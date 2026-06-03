from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

try:  # pragma: no cover
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]


@dataclass(frozen=True)
class SubtitleSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class FrameExtractionResult:
    backend: str
    frame_count: int
    fallback_reason: str | None = None


_SRT_BLOCK_RE = re.compile(
    r"\d+\s+(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\s+(.*?)(?=\n{2,}|\Z)",
    re.DOTALL,
)


def _parse_srt_timestamp(value: str) -> float:
    hh, mm, rest = value.split(":")
    ss, ms = rest.split(",")
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0


def parse_srt(content: str) -> list[SubtitleSegment]:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    segments: list[SubtitleSegment] = []
    for start, end, body in _SRT_BLOCK_RE.findall(normalized):
        text = " ".join(line.strip() for line in body.strip().splitlines() if line.strip())
        if not text:
            continue
        segments.append(
            SubtitleSegment(
                start=_parse_srt_timestamp(start),
                end=_parse_srt_timestamp(end),
                text=text,
            )
        )
    return segments


def load_subtitle_segments(subtitle_file_path: Path) -> list[SubtitleSegment]:
    content = subtitle_file_path.read_text(encoding="utf-8")
    segments = parse_srt(content)
    if segments:
        return segments
    stripped_lines = [
        line.strip()
        for line in content.replace("\r\n", "\n").replace("\r", "\n").splitlines()
        if line.strip()
    ]
    if not stripped_lines:
        return []
    return [SubtitleSegment(start=0.0, end=1.0, text=" ".join(stripped_lines))]


def _format_timestamp(value: float) -> str:
    total_ms = int(round(max(0.0, value) * 1000))
    mm = total_ms // 60000
    rem = total_ms % 60000
    ss = rem // 1000
    ms = rem % 1000
    return f"{mm:02d}:{ss:02d}.{ms:03d}"


def format_subtitle_timeline(segments: list[SubtitleSegment]) -> str:
    lines = ["[SUBTITLE_TIMELINE]"]
    for segment in segments:
        text = " ".join(segment.text.split())
        lines.append(f"[{_format_timestamp(segment.start)} - {_format_timestamp(segment.end)}] {text}")
    lines.append("[/SUBTITLE_TIMELINE]")
    return "\n".join(lines)


def build_sample_timestamps(
    *,
    duration_sec: float,
    sample_interval_sec: float,
    start_sec: float = 0.0,
    max_frames: int | None = None,
) -> list[float]:
    if duration_sec <= 0:
        return []
    if sample_interval_sec <= 0:
        raise ValueError("sample_interval_sec must be positive")
    if start_sec < 0:
        raise ValueError("start_sec must be non-negative")

    timestamps: list[float] = []
    current = start_sec
    while current < duration_sec:
        timestamps.append(round(current, 3))
        current = round(current + sample_interval_sec, 3)
    if max_frames is not None and len(timestamps) > max_frames:
        if max_frames <= 0:
            raise ValueError("max_frames must be positive")
        if max_frames == 1:
            return [round(start_sec, 3)]
        end_sec = max(start_sec, duration_sec - 0.001)
        step = (end_sec - start_sec) / float(max_frames - 1)
        return [round(start_sec + index * step, 3) for index in range(max_frames)]
    return timestamps


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
