from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import get_settings
from .ingest import ingest
from .query import ask
from .store import get_chroma_collection


app = FastAPI(title="VedioRAG", version="0.1.0")


class IngestRequest(BaseModel):
    input_dir: str = Field(..., description="Single-episode video-analyzer result directory.")
    series_id: str
    episode: int = Field(..., ge=1)


class AskRequest(BaseModel):
    question: str
    series_id: str
    current_episode: int = Field(..., ge=1)
    current_time: float = Field(..., ge=0)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
def ingest_endpoint(request: IngestRequest) -> dict[str, Any]:
    try:
        return ingest(Path(request.input_dir), request.series_id, request.episode)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/ask")
def ask_endpoint(request: AskRequest) -> dict[str, Any]:
    try:
        return ask(request.question, request.series_id, request.current_episode, request.current_time)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/collections")
def collections() -> dict[str, Any]:
    try:
        settings = get_settings(require_api_key=False)
        collection = get_chroma_collection(settings)
        rows = collection.get(include=["metadatas"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    episodes: dict[str, dict[str, Any]] = {}
    for metadata in rows.get("metadatas") or []:
        if not metadata:
            continue
        key = f"{metadata.get('series_id')}::E{metadata.get('episode')}"
        item = episodes.setdefault(
            key,
            {
                "series_id": metadata.get("series_id"),
                "episode": metadata.get("episode"),
                "documents": 0,
                "source_types": {},
            },
        )
        item["documents"] += 1
        source_type = metadata.get("source_type")
        item["source_types"][source_type] = item["source_types"].get(source_type, 0) + 1

    return {
        "collection": settings.chroma_collection,
        "chroma_dir": str(settings.chroma_dir),
        "total_documents": len(rows.get("ids") or []),
        "episodes": list(episodes.values()),
    }
