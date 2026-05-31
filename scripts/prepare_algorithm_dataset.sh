#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm"
OUTPUT_ROOT=""
ENV_FILE=".env"
FORCE=0
DRY_RUN=0
LIMIT=0
SHOW_PROGRESS=0
SPLIT_SCENES=0
SCENE_THRESHOLD="27.0"
MIN_SCENE_LEN="15"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/prepare_algorithm_dataset.sh [options]

Options:
  --data-root PATH        Source dataset root. Default: /Users/qinminghao/Desktop/ByteDance/DataForAlgorithm
  --output-root PATH      Optional output root. Default: write artifacts into each epXX directory.
  --env-file PATH         Dotenv file for transcription credentials. Default: .env
  --limit N              Process at most N episodes. Default: all
  --force                Re-run transcription and scene detection even if outputs exist.
  --dry-run              Print commands without running them.
  --show-progress        Show PySceneDetect/ffmpeg progress bars.
  --split-scenes         Also export scenes/*.mp4 clips. Default: only write scene_detection.json.
  --scene-threshold N    PySceneDetect ContentDetector threshold. Default: 27.0
  --min-scene-len N      PySceneDetect minimum scene length in frames. Default: 15
  -h, --help             Show this help.

Outputs per episode:
  <epXX>/video.srt
  <epXX>/video.transcription.json
  <epXX>/video.16k-mono.wav
  <epXX>/scene_detection.json
  <epXX>/scenes/*.mp4 only when --split-scenes is set
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --data-root)
      DATA_ROOT="$2"
      shift 2
      ;;
    --output-root)
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --show-progress)
      SHOW_PROGRESS=1
      shift
      ;;
    --split-scenes)
      SPLIT_SCENES=1
      shift
      ;;
    --scene-threshold)
      SCENE_THRESHOLD="$2"
      shift 2
      ;;
    --min-scene-len)
      MIN_SCENE_LEN="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -d "$DATA_ROOT" ]]; then
  echo "Data root not found: $DATA_ROOT" >&2
  exit 1
fi

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

processed=0
skipped_transcription=0
skipped_scene=0

video_list_file="$(mktemp)"
trap 'rm -f "$video_list_file"' EXIT
find "$DATA_ROOT" -mindepth 3 -maxdepth 3 -type f -name "video.mp4" | sort > "$video_list_file"
episode_count="$(wc -l < "$video_list_file" | tr -d ' ')"

echo "Data root: $DATA_ROOT"
if [[ -n "$OUTPUT_ROOT" ]]; then
  echo "Output root: $OUTPUT_ROOT"
else
  echo "Output mode: in-place epXX directories"
fi
echo "Episode count discovered: ${episode_count}"

while IFS= read -r video_path; do
  ep_dir="$(dirname "$video_path")"
  series_dir="$(dirname "$ep_dir")"
  series_id="$(basename "$series_dir")"
  episode_id="$(basename "$ep_dir")"
  video_id="${series_id}_${episode_id}"
  if [[ -n "$OUTPUT_ROOT" ]]; then
    output_dir="${OUTPUT_ROOT}/${video_id}"
    scene_output_args=(--output-root "$OUTPUT_ROOT")
  else
    output_dir="$ep_dir"
    scene_output_args=(--output-dir "$ep_dir")
  fi

  if [[ "$LIMIT" -gt 0 && "$processed" -ge "$LIMIT" ]]; then
    break
  fi

  echo
  echo "==> ${video_id}"
  echo "    video: ${video_path}"
  mkdir -p "$output_dir"

  transcription_json="${output_dir}/video.transcription.json"
  subtitle_srt="${output_dir}/video.srt"
  if [[ "$FORCE" -eq 0 && -f "$transcription_json" && -f "$subtitle_srt" ]]; then
    echo "    skip transcription: existing ${transcription_json} and ${subtitle_srt}"
    skipped_transcription=$((skipped_transcription + 1))
  else
    run_cmd python scripts/transcribe_video.py "$video_path" \
      --output "$output_dir" \
      --env-file "$ENV_FILE"
  fi

  scene_json="${output_dir}/scene_detection.json"
  scene_args=(
    python scripts/run_scene_detection.py "$video_path"
    --video-id "$video_id"
    "${scene_output_args[@]}"
    --threshold "$SCENE_THRESHOLD"
    --min-scene-len "$MIN_SCENE_LEN"
  )
  if [[ "$SPLIT_SCENES" -eq 0 ]]; then
    scene_args+=(--no-split-scenes)
  fi
  if [[ "$SHOW_PROGRESS" -eq 1 ]]; then
    scene_args+=(--show-progress)
  fi

  if [[ "$FORCE" -eq 0 && -f "$scene_json" ]]; then
    echo "    skip scene detection: existing ${scene_json}"
    skipped_scene=$((skipped_scene + 1))
  else
    run_cmd "${scene_args[@]}"
  fi

  processed=$((processed + 1))
done < "$video_list_file"

echo
echo "Done."
echo "Processed episodes: $processed"
echo "Skipped transcription: $skipped_transcription"
echo "Skipped scene detection: $skipped_scene"
if [[ -n "$OUTPUT_ROOT" ]]; then
  echo "Output root: $OUTPUT_ROOT"
else
  echo "Output mode: in-place epXX directories"
fi
