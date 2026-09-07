#!/usr/bin/env bash
# AvaLimo daily blog publisher. Host cron is the single scheduler.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/blog_cron.log"
LOCK_FILE="/tmp/avalimo-blog-publisher.lock"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Another publisher is running; skipping." >> "$LOG_FILE"
  exit 0
fi

cd "$SCRIPT_DIR"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting blog publisher..." >> "$LOG_FILE"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: repository has uncommitted changes." >> "$LOG_FILE"
  exit 1
fi

git fetch origin main >> "$LOG_FILE" 2>&1
git checkout main >> "$LOG_FILE" 2>&1
git pull --rebase origin main >> "$LOG_FILE" 2>&1

# Backfill up to 7 missed days, then today. auto_blog.py is idempotent
# per date, so already-posted days are cheap no-ops.
FAILED=0
for offset in 7 6 5 4 3 2 1 0; do
  D=$(date -u -d "$offset days ago" +%F)
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ensuring post for ${D}..." >> "$LOG_FILE"
  if ! python3 auto_blog.py --date "$D" >> "$LOG_FILE" 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] FAILED: generation failed for ${D}." >> "$LOG_FILE"
    FAILED=1
  fi
done

if [[ -z "$(git status --porcelain -- blog_posts.json)" ]]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Nothing new to publish." >> "$LOG_FILE"
  [[ "$FAILED" == "0" ]]
  exit $?
fi

title="$(python3 -c 'import json; print(json.load(open("blog_posts.json"))[0]["title"])')"
git add blog_posts.json
git commit -m "auto blog: ${title}" >> "$LOG_FILE" 2>&1
git push origin HEAD:main >> "$LOG_FILE" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: ${title}" >> "$LOG_FILE"
[[ "$FAILED" == "0" ]]
