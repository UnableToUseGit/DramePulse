from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.utils import SubtitleSegment, load_subtitle_segments, probe_video_duration_seconds


DEFAULT_DATA_ROOT = Path("/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm")
DEFAULT_OUTPUT_ROOT = Path("output/subtitle_dialogue_density")


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _char_count(text: str) -> int:
    return len("".join(str(text or "").split()))


def _overlap_seconds(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def _density_level(coverage_ratio: float) -> str:
    if coverage_ratio >= 0.55:
        return "high"
    if coverage_ratio >= 0.25:
        return "medium"
    if coverage_ratio > 0.0:
        return "low"
    return "none"


def _build_range_payload(*, start: float, end: float, segments: list[SubtitleSegment]) -> dict[str, Any]:
    duration = max(0.0, end - start)
    covered_seconds = sum(_overlap_seconds(start, end, segment.start, segment.end) for segment in segments)
    char_count = sum(_char_count(segment.text) for segment in segments)
    return {
        "start_time": _round_time(start),
        "end_time": _round_time(end),
        "duration_sec": _round_time(duration),
        "subtitle_count": len(segments),
        "char_count": char_count,
        "covered_seconds": _round_time(covered_seconds),
        "coverage_ratio": _round_time(covered_seconds / duration) if duration > 0 else 0.0,
        "chars_per_second": _round_time(char_count / duration) if duration > 0 else 0.0,
    }


def build_dialogue_ranges(*, segments: list[SubtitleSegment], merge_gap_sec: float) -> list[dict[str, Any]]:
    if not segments:
        return []
    sorted_segments = sorted(segments, key=lambda segment: (segment.start, segment.end))
    groups: list[list[SubtitleSegment]] = []
    current: list[SubtitleSegment] = []
    current_end = 0.0
    for segment in sorted_segments:
        if not current:
            current = [segment]
            current_end = segment.end
            continue
        if segment.start - current_end <= merge_gap_sec:
            current.append(segment)
            current_end = max(current_end, segment.end)
            continue
        groups.append(current)
        current = [segment]
        current_end = segment.end
    if current:
        groups.append(current)

    ranges: list[dict[str, Any]] = []
    for group in groups:
        start = min(segment.start for segment in group)
        end = max(segment.end for segment in group)
        ranges.append(_build_range_payload(start=start, end=end, segments=group))
    return ranges


def build_silent_ranges(*, dialogue_ranges: list[dict[str, Any]], duration_sec: float, min_silent_sec: float) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    cursor = 0.0
    for dialogue_range in dialogue_ranges:
        start = float(dialogue_range["start_time"])
        if start - cursor >= min_silent_sec:
            ranges.append(
                {
                    "start_time": _round_time(cursor),
                    "end_time": _round_time(start),
                    "duration_sec": _round_time(start - cursor),
                }
            )
        cursor = max(cursor, float(dialogue_range["end_time"]))
    if duration_sec - cursor >= min_silent_sec:
        ranges.append(
            {
                "start_time": _round_time(cursor),
                "end_time": _round_time(duration_sec),
                "duration_sec": _round_time(duration_sec - cursor),
            }
        )
    return ranges


def build_density_windows(*, segments: list[SubtitleSegment], duration_sec: float, window_sec: float) -> list[dict[str, Any]]:
    if duration_sec <= 0 or window_sec <= 0:
        return []
    windows: list[dict[str, Any]] = []
    start = 0.0
    while start < duration_sec:
        end = min(start + window_sec, duration_sec)
        window_segments = [segment for segment in segments if _overlap_seconds(start, end, segment.start, segment.end) > 0]
        payload = _build_range_payload(start=start, end=end, segments=window_segments)
        duration = float(payload["duration_sec"])
        payload["utterances_per_minute"] = _round_time(len(window_segments) / duration * 60.0) if duration > 0 else 0.0
        payload["density_level"] = _density_level(float(payload["coverage_ratio"]))
        windows.append(payload)
        start = _round_time(end)
    return windows


def analyze_subtitle_segments(
    *,
    video_id: str,
    series_id: str,
    episode_id: str,
    segments: list[SubtitleSegment],
    duration_sec: float | None = None,
    merge_gap_sec: float = 0.75,
    min_silent_sec: float = 1.5,
    window_sec: float = 10.0,
) -> dict[str, Any]:
    subtitle_duration = max((segment.end for segment in segments), default=0.0)
    effective_duration = max(float(duration_sec or 0.0), subtitle_duration)
    dialogue_ranges = build_dialogue_ranges(segments=segments, merge_gap_sec=merge_gap_sec)
    silent_ranges = build_silent_ranges(
        dialogue_ranges=dialogue_ranges,
        duration_sec=effective_duration,
        min_silent_sec=min_silent_sec,
    )
    density_windows = build_density_windows(
        segments=segments,
        duration_sec=effective_duration,
        window_sec=window_sec,
    )
    return {
        "video_id": video_id,
        "series_id": series_id,
        "episode_id": episode_id,
        "created_at": now_iso(),
        "duration_sec": _round_time(effective_duration),
        "subtitle_count": len(segments),
        "dialogue_range_count": len(dialogue_ranges),
        "silent_range_count": len(silent_ranges),
        "window_sec": window_sec,
        "merge_gap_sec": merge_gap_sec,
        "min_silent_sec": min_silent_sec,
        "dialogue_ranges": dialogue_ranges,
        "silent_ranges": silent_ranges,
        "density_windows": density_windows,
    }


def discover_subtitle_episodes(data_root: Path) -> list[tuple[str, str, str, Path, Path | None]]:
    episodes: list[tuple[str, str, str, Path, Path | None]] = []
    for subtitle_path in sorted(data_root.glob("*/ep*/video.srt")):
        episode_dir = subtitle_path.parent
        series_id = episode_dir.parent.name
        episode_id = episode_dir.name
        video_id = f"{series_id}_{episode_id}"
        video_path = episode_dir / "video.mp4"
        episodes.append((video_id, series_id, episode_id, subtitle_path, video_path if video_path.exists() else None))
    return episodes


def write_episode_analysis(*, output_root: Path, payload: dict[str, Any]) -> Path:
    output_dir = output_root / str(payload["video_id"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "subtitle_dialogue_density.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def build_summary(*, output_root: Path, episode_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "created_at": now_iso(),
        "output_root": str(output_root),
        "episode_count": len(episode_payloads),
        "total_subtitle_count": sum(int(payload["subtitle_count"]) for payload in episode_payloads),
        "total_dialogue_range_count": sum(int(payload["dialogue_range_count"]) for payload in episode_payloads),
        "total_silent_range_count": sum(int(payload["silent_range_count"]) for payload in episode_payloads),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze subtitle dialogue density and silent gaps.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--series-id", help="Only analyze one series id, for example beiwang.")
    parser.add_argument("--episode-id", help="Only analyze one episode id, for example ep01.")
    parser.add_argument("--video-id", help="Only analyze one exact video id, for example beiwang_ep01.")
    parser.add_argument("--window-sec", type=float, default=10.0)
    parser.add_argument("--merge-gap-sec", type=float, default=0.75)
    parser.add_argument("--min-silent-sec", type=float, default=1.5)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_root: Path = args.output_root
    episode_payloads: list[dict[str, Any]] = []
    for video_id, series_id, episode_id, subtitle_path, video_path in discover_subtitle_episodes(args.data_root):
        if args.series_id and series_id != args.series_id:
            continue
        if args.episode_id and episode_id != args.episode_id:
            continue
        if args.video_id and video_id != args.video_id:
            continue
        segments = load_subtitle_segments(subtitle_path)
        duration_sec = probe_video_duration_seconds(video_path) if video_path is not None else None
        payload = analyze_subtitle_segments(
            video_id=video_id,
            series_id=series_id,
            episode_id=episode_id,
            segments=segments,
            duration_sec=duration_sec,
            merge_gap_sec=args.merge_gap_sec,
            min_silent_sec=args.min_silent_sec,
            window_sec=args.window_sec,
        )
        write_episode_analysis(output_root=output_root, payload=payload)
        episode_payloads.append(payload)

    output_root.mkdir(parents=True, exist_ok=True)
    summary = build_summary(output_root=output_root, episode_payloads=episode_payloads)
    (output_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote subtitle dialogue density analysis for {len(episode_payloads)} episodes to {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
