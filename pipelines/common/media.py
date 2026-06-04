from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Any

try:  # pragma: no cover
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]


@dataclass(frozen=True)
class FrameExtractionResult:
    backend: str
    frame_count: int
    fallback_reason: str | None = None


def _prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("*.png"):
        old.unlink(missing_ok=True)


def _count_frames(output_dir: Path) -> int:
    return len(list(output_dir.glob("*.png")))


def _normalize_timestamps(timestamps_seconds: list[float]) -> list[float]:
    return sorted({max(0.0, round(float(ts), 3)) for ts in timestamps_seconds})


def _downscale_frame_if_needed(frame: Any, *, max_height: int = 720) -> Any:
    shape = getattr(frame, "shape", None)
    if not shape or len(shape) < 2:
        return frame
    height = int(shape[0])
    width = int(shape[1])
    if max_height <= 0:
        raise ValueError("max_height must be positive")
    if height <= 0 or width <= 0 or height <= max_height or cv2 is None:
        return frame
    scale = max_height / float(height)
    target_width = max(2, int(round((width * scale) / 2.0) * 2))
    return cv2.resize(frame, (target_width, max_height))


def _extract_timestamps_with_opencv(
    *,
    video_path: Path,
    output_dir: Path,
    timestamps_seconds: list[float],
    max_height: int = 720,
) -> FrameExtractionResult:
    if cv2 is None:
        raise RuntimeError("OpenCV is not available")
    timestamps = _normalize_timestamps(timestamps_seconds)
    if not timestamps:
        return FrameExtractionResult(backend="opencv_timestamp", frame_count=0)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    saved = 0
    try:
        for ts in timestamps:
            cap.set(cv2.CAP_PROP_POS_MSEC, float(ts) * 1000.0)
            ok, frame = cap.read()
            if not ok:
                continue
            out_path = output_dir / f"t_{int(round(ts * 1000)):09d}.png"
            frame = _downscale_frame_if_needed(frame, max_height=max_height)
            if cv2.imwrite(str(out_path), frame):
                saved += 1
    finally:
        cap.release()
    return FrameExtractionResult(backend="opencv_timestamp", frame_count=saved)


def _extract_timestamps_with_ffmpeg(
    *,
    video_path: Path,
    output_dir: Path,
    timestamps_seconds: list[float],
    max_height: int = 720,
) -> FrameExtractionResult:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required for fallback frame extraction")
    for ts in _normalize_timestamps(timestamps_seconds):
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(ts),
            "-i",
            str(video_path),
            "-vf",
            f"scale=-2:{max_height}:force_original_aspect_ratio=decrease",
            "-frames:v",
            "1",
            str(output_dir / f"t_{int(round(ts * 1000)):09d}.png"),
        ]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to extract frame at {ts}s with ffmpeg: {result.stdout[-300:]}")
    return FrameExtractionResult(backend="ffmpeg_timestamp_fallback", frame_count=_count_frames(output_dir))


def extract_frames_at_timestamps(
    *,
    video_path: Path,
    output_dir: Path,
    timestamps_seconds: list[float],
    max_height: int = 720,
) -> FrameExtractionResult:
    _prepare_output_dir(output_dir)
    try:
        return _extract_timestamps_with_opencv(
            video_path=video_path,
            output_dir=output_dir,
            timestamps_seconds=timestamps_seconds,
            max_height=max_height,
        )
    except Exception as exc:  # noqa: BLE001
        _prepare_output_dir(output_dir)
        fallback = _extract_timestamps_with_ffmpeg(
            video_path=video_path,
            output_dir=output_dir,
            timestamps_seconds=timestamps_seconds,
            max_height=max_height,
        )
        return FrameExtractionResult(
            backend=fallback.backend,
            frame_count=fallback.frame_count,
            fallback_reason=str(exc),
        )


def probe_video_duration_seconds(video_path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    try:
        return float((result.stdout or "").strip())
    except ValueError:
        return None
