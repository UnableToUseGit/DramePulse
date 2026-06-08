from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.common import extract_frames_at_timestamps, probe_video_duration_seconds
from pipelines.story_chapter.baseline_mllm import build_frame_timestamps

try:  # pragma: no cover
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]


def _validate_positive_int(value: int, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive.")


def _probe_frame_size(path: Path) -> tuple[int, int]:
    if cv2 is None:
        raise RuntimeError("OpenCV is required to build storyboard sheets.")
    frame = cv2.imread(str(path))
    if frame is None:
        raise RuntimeError(f"Failed to read frame image: {path}")
    height, width = frame.shape[:2]
    return int(width), int(height)


def _resolve_frame_height(frame_paths: Sequence[Path], *, frame_width: int, frame_height: int | None) -> int:
    if frame_height is not None:
        _validate_positive_int(frame_height, "frame_height")
        return frame_height
    source_width, source_height = _probe_frame_size(frame_paths[0])
    if source_width <= 0 or source_height <= 0:
        raise RuntimeError(f"Invalid frame size: {frame_paths[0]}")
    return max(1, int(round(frame_width * (source_height / float(source_width)))))


def _load_and_resize_frame(path: Path, *, frame_width: int, frame_height: int):
    if cv2 is None:
        raise RuntimeError("OpenCV is required to build storyboard sheets.")
    frame = cv2.imread(str(path))
    if frame is None:
        raise RuntimeError(f"Failed to read frame image: {path}")
    return cv2.resize(frame, (frame_width, frame_height), interpolation=cv2.INTER_AREA)


def _sheet_url(*, url_prefix: str, sheet_name: str) -> str:
    return f"{url_prefix.rstrip('/')}/{sheet_name}" if url_prefix else sheet_name


def build_storyboard_from_frames(
    *,
    video_id: str,
    frame_paths: Sequence[Path],
    output_dir: Path,
    interval_seconds: float,
    frame_width: int,
    frame_height: int | None,
    columns: int,
    rows: int,
    url_prefix: str,
) -> Path:
    if not frame_paths:
        raise ValueError("Storyboard generation requires at least one frame.")
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive.")
    _validate_positive_int(frame_width, "frame_width")
    _validate_positive_int(columns, "columns")
    _validate_positive_int(rows, "rows")
    if np is None:
        raise RuntimeError("NumPy is required to build storyboard sheets.")
    resolved_frame_height = _resolve_frame_height(frame_paths, frame_width=frame_width, frame_height=frame_height)

    output_dir.mkdir(parents=True, exist_ok=True)
    for old_sheet in output_dir.glob("sheet_*.jpg"):
        old_sheet.unlink(missing_ok=True)

    cells_per_sheet = columns * rows
    sheets: list[dict[str, object]] = []
    ordered_frames = list(frame_paths)
    for sheet_index, start_index in enumerate(range(0, len(ordered_frames), cells_per_sheet)):
        sheet_name = f"sheet_{sheet_index:03d}.jpg"
        sheet_path = output_dir / sheet_name
        sheet_frame_paths = ordered_frames[start_index : start_index + cells_per_sheet]
        canvas = np.zeros((resolved_frame_height * rows, frame_width * columns, 3), dtype=np.uint8)
        for cell_index, frame_path in enumerate(sheet_frame_paths):
            row = cell_index // columns
            col = cell_index % columns
            frame = _load_and_resize_frame(frame_path, frame_width=frame_width, frame_height=resolved_frame_height)
            y0 = row * resolved_frame_height
            x0 = col * frame_width
            canvas[y0 : y0 + resolved_frame_height, x0 : x0 + frame_width] = frame
        if not cv2.imwrite(str(sheet_path), canvas):
            raise RuntimeError(f"Failed to write storyboard sheet: {sheet_path}")
        sheets.append(
            {
                "url": _sheet_url(url_prefix=url_prefix, sheet_name=sheet_name),
                "start_time": round(start_index * interval_seconds, 3),
                "frame_count": len(sheet_frame_paths),
            }
        )

    manifest = {
        "video_id": video_id,
        "interval_seconds": float(interval_seconds),
        "frame_width": int(frame_width),
        "frame_height": int(resolved_frame_height),
        "columns": int(columns),
        "rows": int(rows),
        "sheets": sheets,
    }
    manifest_path = output_dir / "storyboard_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _build_timestamps(duration_seconds: float, interval_seconds: float) -> list[float]:
    return build_frame_timestamps(duration_seconds, frame_interval_seconds=interval_seconds, max_frames=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate storyboard sprite sheets for player timeline preview.")
    parser.add_argument("video_id", help="Video id written into storyboard_manifest.json.")
    parser.add_argument("--video", type=Path, required=True, help="Path to source video.mp4.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for storyboard sheets and manifest.")
    parser.add_argument("--url-prefix", default="", help="URL prefix used in manifest sheet URLs.")
    parser.add_argument("--interval-seconds", type=float, default=1.0, help="Preview frame interval in seconds.")
    parser.add_argument("--frame-width", type=int, default=160, help="Storyboard cell width.")
    parser.add_argument(
        "--frame-height",
        type=int,
        default=None,
        help="Storyboard cell height. Omit to preserve the source video aspect ratio.",
    )
    parser.add_argument("--columns", type=int, default=5, help="Sprite sheet columns.")
    parser.add_argument("--rows", type=int, default=5, help="Sprite sheet rows.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    duration_seconds = probe_video_duration_seconds(args.video)
    if duration_seconds is None or duration_seconds <= 0:
        raise ValueError(f"Cannot probe video duration: {args.video}")
    timestamps = _build_timestamps(duration_seconds, args.interval_seconds)
    with tempfile.TemporaryDirectory() as tmpdir:
        frame_dir = Path(tmpdir) / "frames"
        extract_frames_at_timestamps(
            video_path=args.video,
            output_dir=frame_dir,
            timestamps_seconds=timestamps,
            max_height=max(args.frame_height or args.frame_width, 1),
        )
        frame_paths = sorted(frame_dir.glob("*.png"))
        manifest_path = build_storyboard_from_frames(
            video_id=args.video_id,
            frame_paths=frame_paths,
            output_dir=args.output_dir,
            interval_seconds=args.interval_seconds,
            frame_width=args.frame_width,
            frame_height=args.frame_height,
            columns=args.columns,
            rows=args.rows,
            url_prefix=args.url_prefix,
        )
    print(f"Wrote storyboard manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
