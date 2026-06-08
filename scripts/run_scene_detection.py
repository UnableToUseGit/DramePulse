from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Callable, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@dataclass(frozen=True)
class LocalVideo:
    video_id: str
    title: str
    video_path: Path


SceneList = Sequence[tuple[object, object]]
DetectScenes = Callable[[Path, float, int, bool], SceneList]
SplitScenes = Callable[[Path, SceneList, Path, str, bool], list[Path]]


def resolve_video_input(video_path: Path, video_id: str | None = None) -> LocalVideo:
    resolved_path = video_path.expanduser().resolve()
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Video file not found: {resolved_path}")
    resolved_video_id = (video_id or resolved_path.stem).strip()
    if not resolved_video_id:
        raise ValueError("video_id must not be empty")
    return LocalVideo(video_id=resolved_video_id, title=resolved_video_id, video_path=resolved_path)


def run_pyscenedetect(video_path: Path, threshold: float, min_scene_len: int, show_progress: bool) -> SceneList:
    try:
        from scenedetect import ContentDetector, detect
    except ModuleNotFoundError as exc:
        raise RuntimeError("PySceneDetect is not installed in the current Python environment.") from exc

    return detect(
        str(video_path),
        ContentDetector(threshold=threshold, min_scene_len=min_scene_len),
        show_progress=show_progress,
        start_in_scene=True,
    )


def split_video_segments(
    video_path: Path,
    scenes: SceneList,
    output_dir: Path,
    video_id: str,
    show_progress: bool,
) -> list[Path]:
    if not scenes:
        return []
    try:
        from scenedetect import split_video_ffmpeg
    except ModuleNotFoundError as exc:
        raise RuntimeError("PySceneDetect is not installed in the current Python environment.") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    for stale_clip in output_dir.glob(f"{video_id}_scene_*.mp4"):
        stale_clip.unlink()
    return_code = split_video_ffmpeg(
        str(video_path),
        scenes,
        output_dir=output_dir,
        output_file_template=f"{video_id}_scene_$SCENE_NUMBER.mp4",
        video_name=video_id,
        show_progress=show_progress,
    )
    if return_code != 0:
        raise RuntimeError(f"ffmpeg failed to split {video_id}, return code: {return_code}")
    return sorted(output_dir.glob(f"{video_id}_scene_*.mp4"))


def _round_seconds(value: float) -> float:
    return round(float(value), 3)


def build_scene_payload(video_id: str, scenes: SceneList, clip_paths: Sequence[Path], video_output_dir: Path) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for index, (start, end) in enumerate(scenes, start=1):
        start_seconds = _round_seconds(getattr(start, "seconds"))
        end_seconds = _round_seconds(getattr(end, "seconds"))
        clip_path = clip_paths[index - 1] if index - 1 < len(clip_paths) else None
        payload.append(
            {
                "scene_id": f"{video_id}_scene_{index:03d}",
                "index": index,
                "start_time": start_seconds,
                "end_time": end_seconds,
                "duration": _round_seconds(end_seconds - start_seconds),
                "start_frame": int(getattr(start, "frame_num")),
                "end_frame": int(getattr(end, "frame_num")),
                "start_timecode": str(start.get_timecode()),
                "end_timecode": str(end.get_timecode()),
                "clip_path": str(clip_path.relative_to(video_output_dir)) if clip_path else None,
            }
        )
    return payload


def detect_video(
    video: LocalVideo,
    *,
    output_root: Path,
    output_dir: Path | None = None,
    threshold: float,
    min_scene_len: int,
    show_progress: bool,
    split_segments: bool = True,
    detect_scenes: DetectScenes = run_pyscenedetect,
    split_scenes: SplitScenes = split_video_segments,
) -> Path:
    video_output_dir = output_dir if output_dir is not None else output_root / video.video_id
    scenes_output_dir = video_output_dir / "scenes"
    video_output_dir.mkdir(parents=True, exist_ok=True)

    scenes = list(detect_scenes(video.video_path, threshold, min_scene_len, show_progress))
    clip_paths = (
        split_scenes(video.video_path, scenes, scenes_output_dir, video.video_id, show_progress)
        if split_segments
        else []
    )

    payload = {
        "video_id": video.video_id,
        "title": video.title,
        "video_path": str(video.video_path),
        "detector": {
            "type": "content",
            "threshold": threshold,
            "min_scene_len": min_scene_len,
        },
        "scene_count": len(scenes),
        "clip_dir": "scenes",
        "scenes": build_scene_payload(video.video_id, scenes, clip_paths, video_output_dir),
    }
    output_path = video_output_dir / "scene_detection.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect and split scenes for one local video file.")
    parser.add_argument("video_path", type=Path, help="Path to the local video file.")
    parser.add_argument("--video-id", help="Output video_id. Defaults to the video file stem.")
    parser.add_argument("--output-root", type=Path, default=Path("output"), help="Directory for scene detection outputs.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Exact directory for scene_detection.json. Overrides --output-root.")
    parser.add_argument("--threshold", type=float, default=27.0, help="PySceneDetect ContentDetector threshold.")
    parser.add_argument("--min-scene-len", type=int, default=15, help="Minimum scene length in frames.")
    parser.add_argument("--show-progress", action="store_true", help="Show PySceneDetect/ffmpeg progress bars.")
    parser.add_argument("--no-split-scenes", action="store_true", help="Only write scene_detection.json; do not export scene mp4 clips.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    video = resolve_video_input(args.video_path, video_id=args.video_id)
    output_path = detect_video(
        video,
        output_root=args.output_root,
        output_dir=args.output_dir,
        threshold=args.threshold,
        min_scene_len=args.min_scene_len,
        show_progress=args.show_progress,
        split_segments=not args.no_split_scenes,
    )
    print(f"Wrote scene detection for {video.video_id}: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
