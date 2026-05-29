"""기존 SaaS(브로제이·다짐) → HiFIS 회원·PT 일괄 import 스크립트.

사장님 SaaS export 파일은 .xls 확장자지만 내부는 HTML 테이블 (pandas.read_html 사용).
한 셀에 회원의 모든 이용권·대여권 이력이 들어있어 파서로 활성 항목만 추출.

용도:
    docker compose exec app python scripts/import_members.py <엑셀파일> --branch <지점명> [--dry-run]

예시:
    docker compose exec app python scripts/import_members.py /tmp/members.xls --branch "피트니스스타 화순점" --dry-run

엑셀 헤더 (브로제이 표준):
    상태 | 이름 | 생년월일 | 나이 | 연락처 | 보유 이용권 | 보유 대여권 |
    구독 플랜 | 락커룸/락커번호 | 구분 | 최종 만료일 | 최근 구매일 | 최근출석일 |
    BROJ 운톡 | 출석번호 | 특이사항 | 운동목적 | 방문경로 | 상담 담당자 | 간단 주소

처리 정책:
- 미등록 상태는 import 제외
- PT 키워드(`퍼스널`·`1:1`·`2:1`·`PT`) 포함 이용권은 PTApplication으로 분리
- 일반 회원권은 Member로
- 한 사람이 둘 다 보유하면 Member + PTApplication 둘 다 INSERT
- 회원권/락커/운동복 이름이 HiFIS DB에 매핑 안 되면 실패 row로 리포트
- final_price는 매핑된 회원권 + 락커 + 운동복의 cash_price 합산 자동 계산
- 성별·결제정보·운동목적 같은 누락 컬럼은 NULL로 박음 (사장님이 사후 입력)

옵션:
    --branch <지점명>: 지점 이름 (필수, Branch.name 정확히 일치)
    --dry-run: 검증만 수행, INSERT 안 함
"""
import argparse
import csv
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo

# 어디서 실행되든 (docker compose exec, 호스트 등) app 모듈 import되게
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 모든 모델 로드 (FK 해석)
import app.main  # noqa: F401

from bs4 import BeautifulSoup

from app.db.session import SessionLocal
from app.models.branch import Branch
from app.models.passes.clothes import ClothesPass
from app.models.passes.locker import LockerPass
from app.models.passes.membership import MembershipPass
from app.models.passes.pt import PTPass
from app.models.registrations.member import Member
from app.models.registrations.pt_application import PTApplication
from app.utils.validators import is_valid_phone, normalize_phone


_KST = ZoneInfo("Asia/Seoul")

# 엑셀 상태 → MemberStatus
_STATUS_MAP = {
    "활성": "REGISTERED",
    "임박": "REGISTERED",
    "홀딩": "HELD",
    # "미등록"은 제외
}

# 엑셀 방문경로 → Referral
_REFERRAL_MAP = {
    "SNS": "INSTAGRAM",
    "간판 또는 현수막": "BANNER",
    "지인추천": "FRIEND",
    "직원소개": "FRIEND",
    "기타": "OTHER",
    "선택 안함": "OTHER",
    "-": "OTHER",
}

# 엑셀 운동목적 → Motivation (없으면 NULL로 박음)
_MOTIVATION_MAP = {
    "체형교정": "POSTURE_CORRECTION",
    "다이어트": "WEIGHT_LOSS",
    "체중감량": "WEIGHT_LOSS",
    "근육 증가": "MUSCLE_GAIN",
    "건강 개선": "HEALTH_IMPROVEMENT",
    "스트레스 해소": "STRESS_RELIEF",
    "외모 변화": "APPEARANCE",
    "주변 권유": "RECOMMENDATION",
    "부상 / 통증 예방": "INJURY_PREVENTION",
    # "선택 안함"은 NULL
}

# PT 키워드 — 이용권 이름에 포함되면 PTApplication으로 분리
_PT_KEYWORDS = ["퍼스널", "PT", "1:1", "2:1", "1대1", "2대1"]

# 활성 분류 — 이 표시가 붙은 이용권만 추출
_ACTIVE_STATES = {"활성", "임박", "홀딩"}

# "(상태)" 포함 이용권 패턴: "이용권명(상태) YYYY.MM.DD ~ YYYY.MM.DD"
_PASS_PATTERN = re.compile(
    r"(.+?)\(([^)]+)\)\s*"
    r"(\d{4}\.\d{2}\.\d{2})\s*~\s*(\d{4}\.\d{2}\.\d{2})"
)


class ParsedPass(NamedTuple):
    """이용권/대여권 파싱 결과."""
    name: str          # 이용권 이름 (괄호 제외)
    state: str         # 활성·임박·홀딩·만료·예정·status 없음 등
    start_date: date
    end_date: date


def _parse_date(s: str) -> date | None:
    """`2026.05.27` → date"""
    try:
        return datetime.strptime(s.strip(), "%Y.%m.%d").date()
    except (ValueError, AttributeError):
        return None


def _parse_birth_date(v) -> date | None:
    """생년월일 셀 (`1988.04.28` 문자열) → date"""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return _parse_date(str(v))


def parse_passes(cell: str) -> list[ParsedPass]:
    """한 셀의 이용권 이력 문자열에서 모든 이용권 추출.

    예: "(1개월) 이벤트 당첨자(활성) 2026.05.26 ~ 2026.11.25 1개월(만료) 2023.12.06 ~ 2024.01.05"
        → [(이름="(1개월) 이벤트 당첨자", 상태="활성", ...), (이름="1개월", 상태="만료", ...)]
    """
    if not cell:
        return []
    results = []
    for m in _PASS_PATTERN.finditer(str(cell)):
        name = m.group(1).strip()
        state = m.group(2).strip()
        sd = _parse_date(m.group(3))
        ed = _parse_date(m.group(4))
        if sd and ed:
            results.append(ParsedPass(name=name, state=state, start_date=sd, end_date=ed))
    return results


def filter_active(passes: list[ParsedPass]) -> list[ParsedPass]:
    """활성·임박·홀딩 상태인 것만 반환."""
    return [p for p in passes if p.state in _ACTIVE_STATES]


def is_pt_pass(name: str) -> bool:
    """이용권 이름에 PT 키워드 포함 여부."""
    return any(k in name for k in _PT_KEYWORDS)


def _normalize(s: str) -> str:
    """이름 매칭용 정규화 - 공백·탭 차이 무시 ('학생 1개월' = '학생1개월')."""
    return "".join(s.split())


def lookup_membership_pass(
    name: str, branch_id, memberships: dict, pt_passes: dict,
) -> tuple[str, object | None]:
    """이용권 이름으로 회원권 또는 PT 수강권 검색.

    반환: (도메인: 'MEMBER' / 'PT' / 'UNKNOWN', pass 객체 or None)
    """
    key = (branch_id, _normalize(name))
    if is_pt_pass(name):
        pass_obj = pt_passes.get(key)
        return ("PT", pass_obj)
    pass_obj = memberships.get(key)
    return ("MEMBER", pass_obj)


# 락커·운동복 기간 임계값 (일수) → 매핑할 사장님 등록 이름
# 엑셀은 "락커 대여권" 한 종류라 시작~만기 일수로 1개월/3개월/6개월 분류
_LOCKER_BUCKETS = [
    (45, "락커"),         # ~45일 → 1개월짜리
    (135, "락커 3개월"),  # 46~135일 → 3개월
    (None, "락커 6개월"), # 136일+ → 6개월
]
_CLOTHES_BUCKETS = [
    (45, "운동복"),
    (135, "운동복 3개월"),
    (None, "운동복 6개월"),
]


def _bucket_name(days: int, buckets) -> str:
    """기간(일수) → 매핑할 상품 이름."""
    for upper, name in buckets:
        if upper is None or days <= upper:
            return name
    return buckets[-1][1]


def lookup_locker(
    passes: list[ParsedPass], branch_id, lockers: dict, clothes: dict,
) -> tuple[object | None, object | None]:
    """대여권 목록에서 활성 락커·운동복 추출.

    엑셀은 "락커 대여권"·"운동복 대여권" 한 종류 → 기간으로 1/3/6개월 자동 매핑.
    """
    locker = None
    cloth = None
    for p in passes:
        days = (p.end_date - p.start_date).days
        if "락커" in p.name:
            name = _bucket_name(days, _LOCKER_BUCKETS)
            locker = lockers.get((branch_id, _normalize(name)))
        elif "운동복" in p.name:
            name = _bucket_name(days, _CLOTHES_BUCKETS)
            cloth = clothes.get((branch_id, _normalize(name)))
    return locker, cloth


def parse_excel_html(path: str) -> list[dict]:
    """SaaS export(.xls 확장자, 실제는 HTML) → row dict 리스트.

    첫 행을 헤더로, 나머지를 데이터로.
    """
    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    table = soup.find("table")
    if table is None:
        raise RuntimeError("엑셀에서 <table>을 찾을 수 없습니다")

    rows = table.find_all("tr")
    if len(rows) < 2:
        raise RuntimeError("데이터 행 없음")

    headers = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    data: list[dict] = []
    for tr in rows[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if not cells or all(not v for v in cells):
            continue
        data.append(dict(zip(headers, cells)))
    return data


def build_row_data(
    row,
    branch,
    memberships: dict,
    pt_passes: dict,
    lockers: dict,
    clothes: dict,
) -> tuple[list[dict], list[dict], list[str]]:
    """엑셀 1행 → (Member dicts, PTApplication dicts, 경고 메시지).

    한 사람이 회원권 + PT 둘 다 보유하면 양쪽 리스트에 들어감.
    경고는 매핑 실패·누락 정보 등.
    """
    warnings: list[str] = []
    member_rows: list[dict] = []
    pt_rows: list[dict] = []

    # 1. 상태 필터 (미등록 제외)
    excel_status = str(row.get("상태") or "").strip()
    if excel_status not in _STATUS_MAP:
        warnings.append(f"제외(상태={excel_status!r})")
        return [], [], warnings
    hifis_status = _STATUS_MAP[excel_status]

    # 2. 필수 값
    name = str(row.get("이름") or "").strip()
    if not name:
        warnings.append("이름 없음 → 제외")
        return [], [], warnings

    phone_raw = str(row.get("연락처") or "").strip()
    if not is_valid_phone(phone_raw):
        warnings.append(f"전화번호 형식 오류({phone_raw!r}) → 제외")
        return [], [], warnings
    phone = normalize_phone(phone_raw)

    # 생년월일 — 미입력·파싱 실패면 NULL로 박음 (모델 nullable)
    birth_date = _parse_birth_date(row.get("생년월일"))

    # 3. 이용권 파싱
    membership_str = str(row.get("보유 이용권") or "")
    active_passes = filter_active(parse_passes(membership_str))
    if not active_passes:
        warnings.append("활성 이용권 없음 → 제외")
        return [], [], warnings

    rental_str = str(row.get("보유 대여권") or "")
    active_rentals = filter_active(parse_passes(rental_str))

    # 4. 이용권을 회원권/PT로 분리
    member_passes_with_obj: list[tuple[ParsedPass, object | None]] = []
    pt_passes_with_obj: list[tuple[ParsedPass, object | None]] = []
    for p in active_passes:
        domain, pass_obj = lookup_membership_pass(
            p.name, branch.id, memberships, pt_passes,
        )
        if domain == "PT":
            pt_passes_with_obj.append((p, pass_obj))
        else:
            member_passes_with_obj.append((p, pass_obj))

    # 5. 매핑 안 된 이용권 경고
    unmapped_names = [
        p.name for p, obj in member_passes_with_obj + pt_passes_with_obj
        if obj is None
    ]
    if unmapped_names:
        warnings.append(
            f"미매핑 이용권: {unmapped_names} → HiFIS 어드민에 회원권 등록 필요"
        )

    # 6. 대여권 매핑 (락커·운동복)
    locker_obj, clothes_obj = lookup_locker(
        active_rentals, branch.id, lockers, clothes,
    )

    # 7. 공통 필드
    referral_raw = str(row.get("방문경로") or "").strip()
    referral = _REFERRAL_MAP.get(referral_raw, "OTHER")

    motivation_raw = str(row.get("운동목적") or "").strip()
    motivation = _MOTIVATION_MAP.get(motivation_raw)  # None이면 NULL

    address = str(row.get("간단 주소") or "").strip() or "-"

    last_purchase = _parse_birth_date(row.get("최근 구매일"))
    final_expiry = _parse_birth_date(row.get("최종 만료일"))
    if last_purchase is None or final_expiry is None:
        warnings.append("최근 구매일/만료일 파싱 실패 → 제외")
        return [], [], warnings
    # created_at은 KST 정오로 (D+N 트리거 시간 안정성)
    created_at_dt = datetime(
        last_purchase.year, last_purchase.month, last_purchase.day,
        12, 0, 0, tzinfo=_KST,
    )

    # 8. Member dict 생성 (회원권 보유 시)
    if member_passes_with_obj:
        # 첫 번째 활성 회원권을 대표로 박음
        head_pass, head_obj = member_passes_with_obj[0]
        if head_obj is None:
            # 회원권 매핑 안 됨 → Member도 못 만듦 (membership_pass_id 필수)
            warnings.append("회원권 매핑 실패로 Member 미생성")
        else:
            # 회원권이 락커·운동복을 무료제공하면 별도 매핑·가격 합산 차단
            m_eff_locker = None if head_obj.provides_locker else locker_obj
            m_eff_clothes = None if head_obj.provides_clothes else clothes_obj
            if head_obj.provides_locker and locker_obj is not None:
                warnings.append(
                    f"회원권 '{head_obj.name}'에 락커 포함 → 락커 매핑 스킵 (가격 미합산)"
                )
            if head_obj.provides_clothes and clothes_obj is not None:
                warnings.append(
                    f"회원권 '{head_obj.name}'에 운동복 포함 → 운동복 매핑 스킵 (가격 미합산)"
                )

            final_price = head_obj.cash_price
            if m_eff_locker:
                final_price += m_eff_locker.cash_price
            if m_eff_clothes:
                final_price += m_eff_clothes.cash_price

            member_rows.append({
                "branch_id": branch.id,
                "membership_pass_id": head_obj.id,
                "locker_pass_id": m_eff_locker.id if m_eff_locker else None,
                "clothes_pass_id": m_eff_clothes.id if m_eff_clothes else None,
                "total_paid": final_price,  # 마이그는 첫 결제 = 누적
                "name": name,
                "gender": None,  # 엑셀에 없음
                "birth_date": birth_date,
                "phone": phone,
                "address": address,
                "referral": referral,
                "referral_detail": None,
                "payment_method": None,  # 엑셀에 없음
                "final_price": final_price,
                "start_date": head_pass.start_date,
                "end_date": head_pass.end_date,
                "motivation": motivation,
                "agreed_terms": True,  # 가입했다는 사실로 동의 간주
                "agreed_marketing": False,  # 보수적
                "status": hifis_status,
                "created_at": created_at_dt,
            })

    # 9. PTApplication dict 생성 (PT 보유 시)
    if pt_passes_with_obj:
        head_pass, head_obj = pt_passes_with_obj[0]
        if head_obj is None:
            warnings.append("PT 수강권 매핑 실패로 PTApplication 미생성")
        else:
            # 수강권이 락커·운동복을 무료제공하면 별도 매핑·가격 합산 차단
            p_eff_locker = None if head_obj.provides_locker else locker_obj
            p_eff_clothes = None if head_obj.provides_clothes else clothes_obj
            if head_obj.provides_locker and locker_obj is not None:
                warnings.append(
                    f"수강권 '{head_obj.name}'에 락커 포함 → 락커 매핑 스킵 (가격 미합산)"
                )
            if head_obj.provides_clothes and clothes_obj is not None:
                warnings.append(
                    f"수강권 '{head_obj.name}'에 운동복 포함 → 운동복 매핑 스킵 (가격 미합산)"
                )

            final_price = head_obj.cash_price
            if p_eff_locker:
                final_price += p_eff_locker.cash_price
            if p_eff_clothes:
                final_price += p_eff_clothes.cash_price

            pt_rows.append({
                "branch_id": branch.id,
                "pt_pass_id": head_obj.id,
                "locker_pass_id": p_eff_locker.id if p_eff_locker else None,
                "clothes_pass_id": p_eff_clothes.id if p_eff_clothes else None,
                "total_paid": final_price,  # 마이그는 첫 결제 = 누적
                "name": name,
                "gender": None,
                "birth_date": birth_date,
                "phone": phone,
                "address": address,
                "referral": referral,
                "referral_detail": None,
                "payment_method": None,
                "final_price": final_price,
                "start_date": head_pass.start_date,
                "end_date": head_pass.end_date,
                "motivation": motivation,
                "notes": None,
                "agreed_notice": True,
                "agreed_marketing": False,
                "status": hifis_status,
                "created_at": created_at_dt,
            })

    return member_rows, pt_rows, warnings


def bulk_insert_silent(db, table_dicts: list[dict], model) -> tuple[int, list[dict]]:
    """알림 없이 일괄 INSERT. savepoint per row.

    반환: (성공 수, 실패 row 리스트)
    """
    success = 0
    failed: list[dict] = []
    for idx, data in enumerate(table_dicts):
        try:
            with db.begin_nested():
                obj = model(**data)
                db.add(obj)
            success += 1
        except Exception as e:
            failed.append({
                "index": idx,
                "name": data.get("name", "?"),
                "error": str(e),
            })
    db.commit()
    return success, failed


def save_failed_csv(failed: list[dict], path: str) -> None:
    if not failed:
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["row", "name", "warnings"])
        writer.writeheader()
        writer.writerows(failed)
    print(f"[!] 실패·경고 {len(failed)}건 → {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="기존 SaaS 회원·PT 일괄 import"
    )
    parser.add_argument("file", help="엑셀 파일 (.xls/.xlsx)")
    parser.add_argument(
        "--branch", required=True,
        help="지점명 (Branch.name 정확히 일치, 예: 피트니스스타 화순점)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="검증만 수행, INSERT 안 함",
    )
    parser.add_argument(
        "--report", default="/tmp/import_failed.csv",
        help="실패·경고 row 리포트 출력 경로 (기본 /tmp/import_failed.csv)",
    )
    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"ERROR: 파일 없음: {args.file}", file=sys.stderr)
        sys.exit(1)

    print(f"[1/5] 엑셀 파싱: {args.file}")
    rows = parse_excel_html(args.file)
    print(f"  → {len(rows)}행 발견")

    print("[2/5] 지점·상품 lookup")
    db = SessionLocal()
    try:
        branch = db.query(Branch).filter(Branch.name == args.branch).first()
        if branch is None:
            print(f"ERROR: 지점 없음: {args.branch!r}", file=sys.stderr)
            print(f"  HiFIS DB 등록 지점: "
                  f"{[b.name for b in db.query(Branch).all()]}", file=sys.stderr)
            sys.exit(1)

        # 정규화된 이름을 키로 (공백 차이 무시 — 사장님 등록명 vs 엑셀명)
        memberships = {
            (p.branch_id, _normalize(p.name)): p
            for p in db.query(MembershipPass).filter(
                MembershipPass.branch_id == branch.id
            ).all()
        }
        pt_passes = {
            (p.branch_id, _normalize(p.name)): p
            for p in db.query(PTPass).filter(PTPass.branch_id == branch.id).all()
        }
        lockers = {
            (p.branch_id, _normalize(p.name)): p
            for p in db.query(LockerPass).filter(
                LockerPass.branch_id == branch.id
            ).all()
        }
        clothes = {
            (p.branch_id, _normalize(p.name)): p
            for p in db.query(ClothesPass).filter(
                ClothesPass.branch_id == branch.id
            ).all()
        }
        print(f"  → 회원권 {len(memberships)}개, PT {len(pt_passes)}개, "
              f"락커 {len(lockers)}개, 운동복 {len(clothes)}개")

        print("[3/5] 행별 매핑·검증")
        all_member_rows: list[dict] = []
        all_pt_rows: list[dict] = []
        failed: list[dict] = []
        unmapped_passes: set[str] = set()  # 매핑 안 된 회원권 이름 집계

        for idx, row in enumerate(rows):
            try:
                m_rows, p_rows, ws = build_row_data(
                    row, branch, memberships, pt_passes, lockers, clothes,
                )
                all_member_rows.extend(m_rows)
                all_pt_rows.extend(p_rows)

                # 미매핑 회원권명 집계
                for w in ws:
                    if "미매핑 이용권" in w:
                        for n in re.findall(r"'([^']+)'", w):
                            unmapped_passes.add(n)

                # 제외·실패 row 기록
                if not m_rows and not p_rows:
                    failed.append({
                        "row": idx + 2,
                        "name": str(row.get("이름") or "?"),
                        "warnings": "; ".join(ws),
                    })
            except Exception as e:
                failed.append({
                    "row": idx + 2,
                    "name": str(row.get("이름") or "?"),
                    "warnings": f"예외: {e}",
                })

        print(f"  → Member 검증 OK: {len(all_member_rows)}")
        print(f"  → PTApplication 검증 OK: {len(all_pt_rows)}")
        print(f"  → 제외·실패: {len(failed)}")

        if unmapped_passes:
            print()
            print(f"[!] 매핑 안 된 회원권명 {len(unmapped_passes)}종 — "
                  f"HiFIS 어드민에 등록 필요:")
            for n in sorted(unmapped_passes):
                kind = "PT" if is_pt_pass(n) else "Member"
                print(f"  [{kind}] {n!r}")

        if args.dry_run:
            print()
            print("DRY-RUN 종료 — DB 변경 없음")
            save_failed_csv(failed, args.report)
            return

        if unmapped_passes:
            print()
            print("⚠️  매핑 안 된 회원권이 있어 일부 row가 제외됩니다.")
            print("    어드민에 회원권 등록 후 다시 실행하세요.")

        print()
        print(f"[4/5] Member INSERT ({len(all_member_rows)}건)")
        m_success, m_failed = bulk_insert_silent(db, all_member_rows, Member)
        print(f"  → 성공: {m_success}, 실패: {len(m_failed)}")

        print(f"[5/5] PTApplication INSERT ({len(all_pt_rows)}건)")
        p_success, p_failed = bulk_insert_silent(db, all_pt_rows, PTApplication)
        print(f"  → 성공: {p_success}, 실패: {len(p_failed)}")

        print()
        print("=" * 60)
        print(f"✅ Member 성공: {m_success}")
        print(f"✅ PTApplication 성공: {p_success}")
        print(f"❌ 제외·실패: {len(failed) + len(m_failed) + len(p_failed)}")
        print("=" * 60)

        all_failed_for_csv = (
            failed
            + [{"row": "?", "name": f["name"], "warnings": f["error"]}
               for f in m_failed + p_failed]
        )
        save_failed_csv(all_failed_for_csv, args.report)

        if m_success or p_success:
            print()
            print("→ 알림 발송 0건 (silent import)")
            print("→ created_at은 '최근 구매일' 기준 → D+N 트리거 자연 처리")
    finally:
        db.close()


if __name__ == "__main__":
    main()
