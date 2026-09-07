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

if python3 auto_blog.py >> "$LOG_FILE" 2>&1; then
  title="$(python3 -c 'import json; print(json.load(open("blog_posts.json"))[0]["title"])')"
  git add blog_posts.json
  git commit -m "auto blog: ${title}" >> "$LOG_FILE" 2>&1
  git push origin HEAD:main >> "$LOG_FILE" 2>&1
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: ${title}" >> "$LOG_FILE"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] FAILED: article generation failed." >> "$LOG_FILE"
  exit 1
fi
