#!/usr/bin/env bash
#
# HiFIS DB 자동 백업 - 친구 홈서버 cron에서 매일 실행
#
# 사용법 (수동):
#   ./scripts/backup_db.sh
#
# cron 등록 (매일 03:00 KST):
#   crontab -e
#   0 3 * * * cd /path/to/HiFIS-Server && ./scripts/backup_db.sh >> backup.log 2>&1
#
# 출력:
#   $BACKUP_DIR/hifis_YYYYMMDD_HHMMSS.dump            (DB)
#   $BACKUP_DIR/hifis_uploads_YYYYMMDD_HHMMSS.tar.gz  (전자서명 PNG)
# 보존: 14일치 유지, 그 이상은 자동 삭제
# 형식: pg_dump custom format (-Fc) - 압축 + 빠른 restore

set -euo pipefail

# 기본 설정 (환경변수로 override 가능)
BACKUP_DIR="${HIFIS_BACKUP_DIR:-$HOME/hifis_backups}"
RETENTION_DAYS="${HIFIS_BACKUP_RETENTION_DAYS:-14}"
DB_SERVICE="${HIFIS_DB_SERVICE:-db}"
DB_USER="${HIFIS_DB_USER:-hifis}"
DB_NAME="${HIFIS_DB_NAME:-hifis_db}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT="$BACKUP_DIR/hifis_${TIMESTAMP}.dump"
UPLOADS_OUTPUT="$BACKUP_DIR/hifis_uploads_${TIMESTAMP}.tar.gz"

echo "[$(date '+%F %T')] DB 백업 시작 → $OUTPUT"

# Docker 컨테이너 안에서 pg_dump 실행 → 호스트 파일로 스트림
docker compose exec -T "$DB_SERVICE" \
    pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --no-owner --no-acl \
    > "$OUTPUT"

SIZE=$(du -h "$OUTPUT" | cut -f1)
echo "[$(date '+%F %T')] DB 백업 완료 - 크기: $SIZE"

# 전자서명 PNG 백업 (uploads/ 디렉토리 존재할 때만)
if [ -d "uploads" ]; then
    echo "[$(date '+%F %T')] uploads 백업 시작 → $UPLOADS_OUTPUT"
    tar -czf "$UPLOADS_OUTPUT" uploads/
    USIZE=$(du -h "$UPLOADS_OUTPUT" | cut -f1)
    echo "[$(date '+%F %T')] uploads 백업 완료 - 크기: $USIZE"
fi

# 14일 넘은 백업 삭제 (DB + uploads 둘 다)
echo "[$(date '+%F %T')] 오래된 백업 정리 (>$RETENTION_DAYS일)"
find "$BACKUP_DIR" -name 'hifis_*.dump' -type f -mtime "+$RETENTION_DAYS" -print -delete
find "$BACKUP_DIR" -name 'hifis_uploads_*.tar.gz' -type f -mtime "+$RETENTION_DAYS" -print -delete

echo "[$(date '+%F %T')] 백업 완료"
