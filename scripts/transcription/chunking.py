from __future__ import annotations

import math
import os
from pathlib import Path
import shutil
import subprocess

from .errors import ProviderExecutionError


def _resolve_tool_path(env_var: str, tool_name: str) -> str:
    configured = os.environ.get(env_var)
    if configured:
        configured = configured.strip()
        if configured:
            return configured
    resolved = shutil.which(tool_name)
    if resolved:
        return resolved
    return tool_name


def prepare_audio_for_transcription(audio_path: Path) -> Path:
    normalized_audio_path = audio_path.parent / f"{audio_path.stem}.16k-mono.wav"
    if normalized_audio_path.exists() and normalized_audio_path.stat().st_size > 0:
        return normalized_audio_path
    command = [
        _resolve_tool_path("FFMPEG_BIN", "ffmpeg"),
        "-y",
        "-i",
        str(audio_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(normalized_audio_path),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise ProviderExecutionError(f"Failed to normalize audio with ffmpeg: {exc}") from exc
    if not normalized_audio_path.exists() or normalized_audio_path.stat().st_size <= 0:
        raise ProviderExecutionError(f"ffmpeg did not produce a normalized WAV file for {audio_path}")
    return normalized_audio_path


def get_audio_duration_seconds(audio_path: Path) -> float:
    command = [
        _resolve_tool_path("FFPROBE_BIN", "ffprobe"),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise ProviderExecutionError(f"Failed to inspect audio duration with ffprobe: {exc}") from exc
    try:
        return float((result.stdout or "0").strip() or 0.0)
    except ValueError as exc:
        raise ProviderExecutionError(f"Invalid audio duration reported by ffprobe for {audio_path}") from exc


def split_audio_by_duration(
    audio_path: Path,
    chunks_dir: Path,
    *,
    chunk_duration_seconds: int,
) -> list[tuple[Path, float]]:
    if chunk_duration_seconds <= 0:
        raise ProviderExecutionError(f"Invalid chunk duration for audio chunking: {chunk_duration_seconds}")
    chunks_dir.mkdir(parents=True, exist_ok=True)
    existing_chunks = sorted(chunks_dir.glob("chunk_*.wav"))
    if not existing_chunks:
        output_pattern = chunks_dir / "chunk_%03d.wav"
        command = [
            _resolve_tool_path("FFMPEG_BIN", "ffmpeg"),
            "-y",
            "-i",
            str(audio_path),
            "-f",
            "segment",
            "-segment_time",
            str(chunk_duration_seconds),
            "-c",
            "copy",
            str(output_pattern),
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise ProviderExecutionError(f"Failed to split audio with ffmpeg: {exc}") from exc
        existing_chunks = sorted(chunks_dir.glob("chunk_*.wav"))
    if not existing_chunks:
        raise ProviderExecutionError(f"ffmpeg did not produce audio chunks for {audio_path}")
    return [(chunk, index * float(chunk_duration_seconds)) for index, chunk in enumerate(existing_chunks)]
