from __future__ import annotations

from scripts.transcription.types import TranscriptSegment


def transcript_segments_to_srt(segments: list[TranscriptSegment]) -> str:
    def fmt(value: float) -> str:
        total_ms = int(round(max(0.0, value) * 1000))
        hh = total_ms // 3600000
        rem = total_ms % 3600000
        mm = rem // 60000
        rem %= 60000
        ss = rem // 1000
        ms = rem % 1000
        return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"

    blocks: list[str] = []
    for idx, segment in enumerate(segments, start=1):
        text = " ".join(segment.text.split())
        if not text:
            continue
        blocks.append(f"{idx}\n{fmt(segment.start)} --> {fmt(segment.end)}\n{text}")
    return "\n\n".join(blocks).strip() + ("\n" if blocks else "")
