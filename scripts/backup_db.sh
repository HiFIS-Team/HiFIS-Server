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
# 출력: $BACKUP_DIR/hifis_YYYYMMDD_HHMMSS.dump
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

echo "[$(date '+%F %T')] DB 백업 시작 → $OUTPUT"

# Docker 컨테이너 안에서 pg_dump 실행 → 호스트 파일로 스트림
docker compose exec -T "$DB_SERVICE" \
    pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --no-owner --no-acl \
    > "$OUTPUT"

SIZE=$(du -h "$OUTPUT" | cut -f1)
echo "[$(date '+%F %T')] 완료 - 크기: $SIZE"

# 14일 넘은 백업 삭제
echo "[$(date '+%F %T')] 오래된 백업 정리 (>$RETENTION_DAYS일)"
find "$BACKUP_DIR" -name 'hifis_*.dump' -type f -mtime "+$RETENTION_DAYS" -print -delete

echo "[$(date '+%F %T')] 백업 완료"
