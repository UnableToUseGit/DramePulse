from __future__ import annotations

import argparse
import array
from dataclasses import dataclass
from html import escape
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Callable, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@dataclass(frozen=True)
class MediaInput:
    media_id: str
    media_path: Path


@dataclass(frozen=True)
class EnergySample:
    time: float
    rms_db: float


@dataclass(frozen=True)
class VisualizationResult:
    output_dir: Path
    energy_json_path: Path
    waveform_svg_path: Path
    spectrogram_png_path: Path


ExtractEnergy = Callable[[Path, float], list[EnergySample]]
WriteSpectrogram = Callable[[Path, Path], None]


def _resolve_tool_path(env_var: str, tool_name: str) -> str:
    configured = os.environ.get(env_var)
    if configured and configured.strip():
        return configured.strip()
    resolved = shutil.which(tool_name)
    return resolved or tool_name


def resolve_media_input(media_path: Path, media_id: str | None = None) -> MediaInput:
    resolved_path = media_path.expanduser().resolve()
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Media file not found: {resolved_path}")
    resolved_media_id = (media_id or resolved_path.stem).strip()
    if not resolved_media_id:
        raise ValueError("media_id must not be empty")
    return MediaInput(media_id=resolved_media_id, media_path=resolved_path)


def extract_energy_samples(media_path: Path, sample_interval: float = 0.1, sample_rate: int = 16000) -> list[EnergySample]:
    if sample_interval <= 0:
        raise ValueError("sample_interval must be greater than 0")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be greater than 0")
    command = [
        _resolve_tool_path("FFMPEG_BIN", "ffmpeg"),
        "-hide_banner",
        "-v",
        "error",
        "-i",
        str(media_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "s16le",
        "-",
    ]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError(f"Failed to extract audio energy with ffmpeg: {exc}") from exc

    pcm = array.array("h")
    pcm.frombytes(result.stdout or b"")
    if sys.byteorder != "little":
        pcm.byteswap()
    window_size = max(1, int(round(sample_rate * sample_interval)))
    samples: list[EnergySample] = []
    for start in range(0, len(pcm), window_size):
        window = pcm[start : start + window_size]
        if not window:
            continue
        mean_square = sum(float(sample) * float(sample) for sample in window) / len(window)
        if mean_square <= 0:
            rms_db = -100.0
        else:
            rms = math.sqrt(mean_square) / 32768.0
            rms_db = max(-100.0, 20.0 * math.log10(rms))
        samples.append(EnergySample(time=round(len(samples) * sample_interval, 3), rms_db=round(rms_db, 3)))
    if not samples:
        raise RuntimeError(f"ffmpeg did not produce PCM audio for {media_path}")
    return samples


def write_spectrogram_png(media_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        _resolve_tool_path("FFMPEG_BIN", "ffmpeg"),
        "-hide_banner",
        "-y",
        "-i",
        str(media_path),
        "-lavfi",
        "showspectrumpic=s=1600x700:legend=1:scale=log",
        str(output_path),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError(f"Failed to write audio spectrogram with ffmpeg: {exc}") from exc
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise RuntimeError(f"ffmpeg did not produce spectrogram image: {output_path}")


def _normalize_energy(rms_db: float, floor_db: float) -> float:
    clamped = max(floor_db, min(0.0, rms_db))
    return (clamped - floor_db) / abs(floor_db)


def write_waveform_svg(samples: Sequence[EnergySample], output_path: Path, *, media_id: str, floor_db: float = -60.0) -> None:
    if not samples:
        raise ValueError("samples must not be empty")
    width = 1600
    height = 420
    pad_x = 48
    pad_y = 54
    chart_width = width - pad_x * 2
    chart_height = height - pad_y * 2
    max_time = max(sample.time for sample in samples) or 1.0

    points: list[str] = []
    for sample in samples:
        x = pad_x + (sample.time / max_time) * chart_width
        normalized = _normalize_energy(sample.rms_db, floor_db)
        y = pad_y + (1.0 - normalized) * chart_height
        points.append(f"{x:.2f},{y:.2f}")

    grid_lines = []
    for index in range(5):
        y = pad_y + (chart_height / 4) * index
        db_value = 0 + (floor_db / 4) * index
        grid_lines.append(
            f'<line x1="{pad_x}" y1="{y:.2f}" x2="{width - pad_x}" y2="{y:.2f}" stroke="#263238" stroke-width="1" />'
        )
        grid_lines.append(f'<text x="12" y="{y + 4:.2f}" fill="#8fa1aa" font-size="12">{db_value:.0f} dB</text>')

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#101315" />
  <text x="{pad_x}" y="30" fill="#f2f0e8" font-size="20" font-family="Avenir Next, PingFang SC, sans-serif" font-weight="700">DramePulse Audio Energy · {escape(media_id)}</text>
  {"".join(grid_lines)}
  <line x1="{pad_x}" y1="{height - pad_y}" x2="{width - pad_x}" y2="{height - pad_y}" stroke="#56626a" stroke-width="1.5" />
  <polyline points="{" ".join(points)}" fill="none" stroke="#f6c85f" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
  <text x="{pad_x}" y="{height - 18}" fill="#8fa1aa" font-size="13">time: 0s - {max_time:.1f}s · floor: {floor_db:.0f} dB</text>
</svg>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")


def build_energy_payload(media: MediaInput, samples: Sequence[EnergySample], sample_interval: float) -> dict[str, object]:
    peak = max(sample.rms_db for sample in samples)
    average = sum(sample.rms_db for sample in samples) / len(samples)
    duration = samples[-1].time if samples else 0.0
    return {
        "media_id": media.media_id,
        "media_path": str(media.media_path),
        "sample_interval": sample_interval,
        "summary": {
            "duration": round(duration, 3),
            "sample_count": len(samples),
            "peak_rms_db": round(peak, 3),
            "average_rms_db": round(average, 3),
        },
        "samples": [{"time": sample.time, "rms_db": sample.rms_db} for sample in samples],
    }


def generate_visualization(
    media: MediaInput,
    *,
    output_root: Path,
    sample_interval: float,
    extract_energy: ExtractEnergy = extract_energy_samples,
    write_spectrogram: WriteSpectrogram = write_spectrogram_png,
) -> VisualizationResult:
    output_dir = output_root / media.media_id / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = extract_energy(media.media_path, sample_interval)
    energy_json_path = output_dir / "energy.json"
    waveform_svg_path = output_dir / "waveform.svg"
    spectrogram_png_path = output_dir / "spectrogram.png"

    energy_json_path.write_text(
        json.dumps(build_energy_payload(media, samples, sample_interval), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_waveform_svg(samples, waveform_svg_path, media_id=media.media_id)
    write_spectrogram(media.media_path, spectrogram_png_path)

    return VisualizationResult(
        output_dir=output_dir,
        energy_json_path=energy_json_path,
        waveform_svg_path=waveform_svg_path,
        spectrogram_png_path=spectrogram_png_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate audio energy and spectrogram visualizations.")
    parser.add_argument("media_path", type=Path, help="Path to a local video or audio file.")
    parser.add_argument("--media-id", help="Output id. Defaults to the input file stem.")
    parser.add_argument("--output-root", type=Path, default=Path("output"), help="Root directory for outputs.")
    parser.add_argument("--sample-interval", type=float, default=0.1, help="Energy sampling interval in seconds.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    media = resolve_media_input(args.media_path, media_id=args.media_id)
    result = generate_visualization(
        media,
        output_root=args.output_root,
        sample_interval=args.sample_interval,
    )
    print(f"Wrote audio visualization for {media.media_id}: {result.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
