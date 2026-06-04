from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class SubtitleSegment:
    start: float
    end: float
    text: str


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
