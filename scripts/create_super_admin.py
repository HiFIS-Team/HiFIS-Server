"""SUPER_ADMIN 계정 생성 CLI

용도:
  - 개발/로컬 초기 셋업
  - 운영 배포 직후 사장님 계정 한 번 생성

사용법 (컨테이너 안):
  대화형:   docker compose exec app python scripts/create_super_admin.py
  인자:    docker compose exec app python scripts/create_super_admin.py \\
              --email admin@hifis.com --password '비번' --name 관리자

운영 시엔 대화형(getpass) 권장 — 비번이 shell history에 안 남음.
"""
import argparse
import getpass
import os
import sys

# 어디서 실행되든 app 모듈 import되게
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# app.main import → 모든 모델·라우터 한 번에 로드 (Admin FK가 다른 모델 참조하므로 필수)
import app.main  # noqa: F401

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.admin.admin import Admin
from app.schemas.enums import AdminRole, AdminStatus


def main() -> None:
    parser = argparse.ArgumentParser(description="SUPER_ADMIN 계정 생성")
    parser.add_argument("--email", help="이메일 (로그인 ID)")
    parser.add_argument("--password", help="비밀번호 (생략 시 입력 받음)")
    parser.add_argument("--name", help="관리자 이름 (예: 관리자, 대표)")
    args = parser.parse_args()

    email = args.email or input("이메일: ").strip()
    password = args.password or getpass.getpass("비밀번호 (8자 이상): ")
    name = args.name or input("이름: ").strip()

    if not email or not password or not name:
        print("ERROR: email, password, name 모두 필요합니다.", file=sys.stderr)
        sys.exit(1)
    if len(password) < 8:
        print("ERROR: 비밀번호는 8자 이상이어야 합니다.", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        if db.query(Admin).filter(Admin.email == email).first() is not None:
            print(f"ERROR: 이미 사용 중인 이메일입니다: {email}", file=sys.stderr)
            sys.exit(1)

        admin = Admin(
            email=email,
            password_hash=hash_password(password),
            name=name,
            role=AdminRole.SUPER_ADMIN.value,
            status=AdminStatus.ACTIVE.value,
            branch_id=None,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print()
        print("=" * 60)
        print("✅ SUPER_ADMIN 생성 완료")
        print("=" * 60)
        print(f"  id     : {admin.id}")
        print(f"  email  : {admin.email}")
        print(f"  name   : {admin.name}")
        print(f"  role   : {admin.role}")
        print(f"  status : {admin.status}")
        print()
        print("→ POST /admin/login 으로 로그인하세요.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
