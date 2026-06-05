#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DATA_ROOT="${DATA_ROOT:-/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_ROOT}/output/storyboards}"

INTERVAL_SECONDS="${INTERVAL_SECONDS:-1.0}"
FRAME_WIDTH="${FRAME_WIDTH:-120}"
COLUMNS="${COLUMNS:-5}"
ROWS="${ROWS:-5}"

SERIES_IDS=(
  "beiwang"
  "jiali_jiawai"
  "nanian_dongzhi"
  "yunmiao_1"
  "tianxia_diyi_wanku"
)

cd "${REPO_ROOT}"

if [[ ! -d "${DATA_ROOT}" ]]; then
  echo "Data root not found: ${DATA_ROOT}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_ROOT}"

for series_id in "${SERIES_IDS[@]}"; do
  for episode_no in 1 2 3 4 5; do
    episode_label="$(printf "ep%02d" "${episode_no}")"
    video_id="${series_id}_${episode_label}"
    video_path="${DATA_ROOT}/${series_id}/${episode_label}/video.mp4"
    output_dir="${OUTPUT_ROOT}/${video_id}"
    url_prefix="/storyboards/${video_id}"

    if [[ ! -f "${video_path}" ]]; then
      echo "Missing video, skip: ${video_path}" >&2
      continue
    fi

    echo "Generating storyboard: ${video_id}"
    python3 scripts/generate_storyboard.py "${video_id}" \
      --video "${video_path}" \
      --output-dir "${output_dir}" \
      --url-prefix "${url_prefix}" \
      --interval-seconds "${INTERVAL_SECONDS}" \
      --frame-width "${FRAME_WIDTH}" \
      --columns "${COLUMNS}" \
      --rows "${ROWS}"
  done
done

echo "Storyboard batch finished. Output root: ${OUTPUT_ROOT}"
