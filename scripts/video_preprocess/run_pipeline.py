from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.common import now_iso
from scripts.run_scene_detection import detect_video, resolve_video_input
from scripts.transcribe_video import transcribe_video_to_srt
from scripts.transcription.chunking import prepare_audio_for_transcription


DEFAULT_OUTPUT_ROOT = Path("output/video_preprocess")
MANIFEST_FILENAME = "video_preprocess_manifest.json"

AudioExtractor = Callable[..., Path]
Transcriber = Callable[..., Path]
SceneDetector = Callable[..., Path]


@dataclass(frozen=True)
class VideoPreprocessResult:
    video_id: str
    output_dir: Path
    audio_path: Path
    subtitle_path: Path
    scene_detection_path: Path
    manifest_path: Path


def _default_extract_audio(*, video_path: Path, output_dir: Path) -> Path:
    return prepare_audio_for_transcription(video_path, output_dir=output_dir)


def _default_transcribe(*, video_path: Path, output_dir: Path, env_path: Path | None) -> Path:
    return transcribe_video_to_srt(video_path=video_path, output_dir=output_dir, env_path=env_path)


def _default_detect_scenes(
    *,
    video_path: Path,
    video_id: str,
    output_dir: Path,
    threshold: float,
    min_scene_len: int,
    show_progress: bool,
    split_segments: bool,
) -> Path:
    return detect_video(
        resolve_video_input(video_path, video_id=video_id),
        output_root=output_dir.parent,
        output_dir=output_dir,
        threshold=threshold,
        min_scene_len=min_scene_len,
        show_progress=show_progress,
        split_segments=split_segments,
    )


def _rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def write_manifest(result: VideoPreprocessResult, *, source_video_path: Path) -> Path:
    payload = {
        "pipeline": "video-preprocess",
        "video_id": result.video_id,
        "source_video_path": str(source_video_path),
        "created_at": now_iso(),
        "artifacts": {
            "audio_path": _rel(result.audio_path, result.output_dir),
            "subtitle_path": _rel(result.subtitle_path, result.output_dir),
            "scene_detection_path": _rel(result.scene_detection_path, result.output_dir),
        },
        "stages": [
            {"name": "audio_extraction", "status": "completed", "output": _rel(result.audio_path, result.output_dir)},
            {"name": "subtitle_transcription", "status": "completed", "output": _rel(result.subtitle_path, result.output_dir)},
            {
                "name": "scene_detection",
                "status": "completed",
                "output": _rel(result.scene_detection_path, result.output_dir),
            },
        ],
    }
    result.manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result.manifest_path


def run_video_preprocess(
    *,
    video_path: Path,
    video_id: str | None = None,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    env_path: Path | None = Path(".env"),
    threshold: float = 27.0,
    min_scene_len: int = 15,
    show_progress: bool = False,
    split_segments: bool = True,
    extract_audio: AudioExtractor = _default_extract_audio,
    transcribe: Transcriber = _default_transcribe,
    detect_scenes: SceneDetector = _default_detect_scenes,
) -> VideoPreprocessResult:
    resolved_video = resolve_video_input(video_path, video_id=video_id)
    output_dir = output_root / resolved_video.video_id
    audio_dir = output_dir / "audio"
    transcription_dir = output_dir / "transcription"
    scene_dir = output_dir / "scene_detection"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{resolved_video.video_id}] audio_extraction start")
    audio_path = extract_audio(video_path=resolved_video.video_path, output_dir=audio_dir)
    print(f"[{resolved_video.video_id}] audio_extraction wrote {audio_path}")

    print(f"[{resolved_video.video_id}] subtitle_transcription start")
    subtitle_path = transcribe(video_path=resolved_video.video_path, output_dir=transcription_dir, env_path=env_path)
    print(f"[{resolved_video.video_id}] subtitle_transcription wrote {subtitle_path}")

    print(f"[{resolved_video.video_id}] scene_detection start")
    scene_detection_path = detect_scenes(
        video_path=resolved_video.video_path,
        video_id=resolved_video.video_id,
        output_dir=scene_dir,
        threshold=threshold,
        min_scene_len=min_scene_len,
        show_progress=show_progress,
        split_segments=split_segments,
    )
    print(f"[{resolved_video.video_id}] scene_detection wrote {scene_detection_path}")

    result = VideoPreprocessResult(
        video_id=resolved_video.video_id,
        output_dir=output_dir,
        audio_path=audio_path,
        subtitle_path=subtitle_path,
        scene_detection_path=scene_detection_path,
        manifest_path=output_dir / MANIFEST_FILENAME,
    )
    write_manifest(result, source_video_path=resolved_video.video_path)
    print(f"[{resolved_video.video_id}] manifest wrote {result.manifest_path}")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local video preprocessing: audio extraction, subtitle transcription, and scene detection."
    )
    parser.add_argument("video_path", type=Path, help="Path to the local source video file.")
    parser.add_argument("--video-id", help="Output video_id. Defaults to the video file stem.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--threshold", type=float, default=27.0, help="PySceneDetect ContentDetector threshold.")
    parser.add_argument("--min-scene-len", type=int, default=15, help="Minimum scene length in frames.")
    parser.add_argument("--show-progress", action="store_true")
    parser.add_argument("--no-split-scenes", action="store_true", help="Write scene JSON only; do not export scene clips.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    run_video_preprocess(
        video_path=args.video_path,
        video_id=args.video_id,
        output_root=args.output_root,
        env_path=args.env_file,
        threshold=args.threshold,
        min_scene_len=args.min_scene_len,
        show_progress=args.show_progress,
        split_segments=not args.no_split_scenes,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
