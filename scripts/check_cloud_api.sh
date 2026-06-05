#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://39.96.219.88:8000}"
VIDEO_ID="${VIDEO_ID:-beiwang_ep01}"
SERIES_ID="${SERIES_ID:-beiwang}"
EPISODE_NO="${EPISODE_NO:-1}"
MAX_DANMAKU_BYTES="${MAX_DANMAKU_BYTES:-4000}"

section() {
  printf '\n=== %s ===\n' "$1"
}

get_json() {
  local url="$1"
  curl -sS --max-time 15 "$url"
}

get_json_limited() {
  local url="$1"
  curl -sS --max-time 15 "$url" | head -c "$MAX_DANMAKU_BYTES"
  printf '\n'
}

get_headers() {
  local url="$1"
  curl -sS -D - -o /dev/null --max-time 15 "$url"
}

section "health"
get_json "${BASE_URL}/api/health"

# section "videos"
# get_json "${BASE_URL}/api/videos"

section "video detail"
get_json "${BASE_URL}/api/videos/${VIDEO_ID}"

# section "video danmaku (truncated)"
# get_json_limited "${BASE_URL}/api/videos/${VIDEO_ID}/danmaku"

section "video interaction plans"
get_json "${BASE_URL}/api/videos/${VIDEO_ID}/interaction-plans"

# section "video stream headers"
# get_headers "${BASE_URL}/api/videos/${VIDEO_ID}/stream"

section "series list"
get_json "${BASE_URL}/api/series"

section "series episodes"
get_json "${BASE_URL}/api/series/${SERIES_ID}/episodes"

section "series episode by number"
get_json "${BASE_URL}/api/series/${SERIES_ID}/episodes/${EPISODE_NO}"

section "home feed"
get_json "${BASE_URL}/api/feed/home"
