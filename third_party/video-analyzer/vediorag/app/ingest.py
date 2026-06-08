import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from llama_index.core import Document

from .config import get_settings
from .store import get_index


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _session_id(input_dir: Path) -> str:
    return input_dir.resolve().name


def _metadata(
    *,
    series_id: str,
    episode: int,
    start_time: float,
    end_time: float,
    source_type: str,
    source_file: str,
    session_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "series_id": series_id,
        "episode": episode,
        "start_time": float(start_time),
        "end_time": float(end_time),
        "source_type": source_type,
        "source_file": source_file,
        "session_id": session_id,
    }
    if extra:
        data.update(extra)
    return data


def build_documents(input_dir: Path, series_id: str, episode: int) -> list[Document]:
    input_dir = input_dir.resolve()
    session_id = _session_id(input_dir)
    documents: list[Document] = []

    analysis = _read_json(input_dir / "analysis.json")
    transcript = _read_json(input_dir / "transcript.json")
    frame_rows = _read_jsonl(input_dir / "frame_analyses.jsonl")

    for idx, segment in enumerate(transcript.get("segments", [])):
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        start = float(segment.get("start") or 0.0)
        end = float(segment.get("end") or start)
        documents.append(
            Document(
                text=text,
                metadata=_metadata(
                    series_id=series_id,
                    episode=episode,
                    start_time=start,
                    end_time=end,
                    source_type="transcript",
                    source_file="transcript.json",
                    session_id=session_id,
                    extra={"chunk_index": idx},
                ),
            )
        )

    for row in frame_rows:
        response = (row.get("response") or "").strip()
        if not response:
            continue
        ts = float(row.get("timestamp") or 0.0)
        documents.append(
            Document(
                text=response,
                metadata=_metadata(
                    series_id=series_id,
                    episode=episode,
                    start_time=ts,
                    end_time=ts,
                    source_type="frame_analysis",
                    source_file="frame_analyses.jsonl",
                    session_id=session_id,
                    extra={
                        "frame_number": int(row.get("frame_number") or 0),
                        "image_path": row.get("image_path") or "",
                    },
                ),
            )
        )

    fusion_path = input_dir / "fusion_result.md"
    fusion_text = fusion_path.read_text(encoding="utf-8").strip() if fusion_path.exists() else ""
    if fusion_text:
        duration = _episode_duration(analysis, transcript, frame_rows)
        documents.append(
            Document(
                text=fusion_text,
                metadata=_metadata(
                    series_id=series_id,
                    episode=episode,
                    start_time=duration,
                    end_time=duration,
                    source_type="episode_summary",
                    source_file="fusion_result.md",
                    session_id=session_id,
                    extra={"available_after_episode_end": True},
                ),
            )
        )

    return documents


def _episode_duration(
    analysis: dict[str, Any],
    transcript: dict[str, Any],
    frame_rows: Iterable[dict[str, Any]],
) -> float:
    ends = [float(s.get("end") or 0.0) for s in transcript.get("segments", [])]
    ends.extend(float(row.get("timestamp") or 0.0) for row in frame_rows)
    metadata = analysis.get("metadata") or {}
    if metadata.get("duration_processed"):
        ends.append(float(metadata["duration_processed"]))
    return max(ends or [0.0])


def ingest(input_dir: Path, series_id: str, episode: int) -> dict[str, Any]:
    settings = get_settings(require_api_key=True)
    documents = build_documents(input_dir, series_id, episode)
    if not documents:
        raise RuntimeError(f"No ingestible documents found in {input_dir}")

    index = get_index(settings)
    for doc in documents:
        index.insert(doc)

    by_type: dict[str, int] = {}
    for doc in documents:
        source_type = str(doc.metadata.get("source_type"))
        by_type[source_type] = by_type.get(source_type, 0) + 1

    return {
        "input_dir": str(input_dir.resolve()),
        "series_id": series_id,
        "episode": episode,
        "documents": len(documents),
        "by_type": by_type,
        "chroma_dir": str(settings.chroma_dir),
        "collection": settings.chroma_collection,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest one video-analyzer result directory into Chroma.")
    parser.add_argument("--input", required=True, type=Path, help="Single-episode analysis result directory.")
    parser.add_argument("--series-id", required=True, help="Series identifier.")
    parser.add_argument("--episode", required=True, type=int, help="Episode number.")
    args = parser.parse_args()

    result = ingest(args.input, args.series_id, args.episode)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
