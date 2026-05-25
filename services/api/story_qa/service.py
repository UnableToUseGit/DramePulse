from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Protocol

from services.api.config import Settings, get_settings


SPOILER_SAFE_PROMPT = """你是短剧剧情问答助手。
只能基于下方检索到的、用户当前观看进度内的资料回答。
不要使用后续剧情、常识猜测或未提供资料补全答案。
如果当前进度内无法确认答案，请明确回答“当前观看进度内无法确认”。
回答使用简体中文，并尽量引用集数、时间点或资料类型。"""


class StoryQaDocument:
    def __init__(self, text: str, metadata: dict[str, Any]) -> None:
        self.text = text
        self.metadata = metadata


class ChromaQueryNode:
    def __init__(self, text: str, metadata: dict[str, Any], score: float | None = None) -> None:
        self._text = text
        self.metadata = metadata
        self.score = score

    def get_text(self) -> str:
        return self._text


class RetrievedNode(Protocol):
    metadata: dict[str, Any]
    score: float | None

    def get_text(self) -> str:
        ...


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


def _episode_duration(
    analysis: dict[str, Any],
    transcript: dict[str, Any],
    frame_rows: Iterable[dict[str, Any]],
) -> float:
    ends = [float(segment.get("end") or 0.0) for segment in transcript.get("segments", [])]
    ends.extend(float(row.get("timestamp") or 0.0) for row in frame_rows)
    metadata = analysis.get("metadata") or {}
    if metadata.get("duration_processed"):
        ends.append(float(metadata["duration_processed"]))
    return max(ends or [0.0])


def build_documents(input_dir: Path, series_id: str, episode: int) -> list[StoryQaDocument]:
    input_dir = input_dir.resolve()
    session_id = input_dir.name
    documents: list[StoryQaDocument] = []

    analysis = _read_json(input_dir / "analysis.json")
    transcript = _read_json(input_dir / "transcript.json")
    frame_rows = _read_jsonl(input_dir / "frame_analyses.jsonl")

    for index, segment in enumerate(transcript.get("segments", [])):
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        start = float(segment.get("start") or 0.0)
        end = float(segment.get("end") or start)
        documents.append(
            StoryQaDocument(
                text=text,
                metadata=_metadata(
                    series_id=series_id,
                    episode=episode,
                    start_time=start,
                    end_time=end,
                    source_type="transcript",
                    source_file="transcript.json",
                    session_id=session_id,
                    extra={"chunk_index": index},
                ),
            )
        )

    for row in frame_rows:
        response = (row.get("response") or "").strip()
        if not response:
            continue
        timestamp = float(row.get("timestamp") or 0.0)
        documents.append(
            StoryQaDocument(
                text=response,
                metadata=_metadata(
                    series_id=series_id,
                    episode=episode,
                    start_time=timestamp,
                    end_time=timestamp,
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
            StoryQaDocument(
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


def is_visible(node: RetrievedNode, current_episode: int, current_time: float) -> bool:
    metadata = node.metadata or {}
    episode = int(metadata.get("episode") or 0)
    end_time = float(metadata.get("end_time") or 0.0)
    return episode < current_episode or (episode == current_episode and end_time <= float(current_time))


def build_prompt(question: str, nodes: list[RetrievedNode]) -> str:
    context = "\n\n".join(
        f"[{node.metadata.get('source_type')} E{node.metadata.get('episode')} "
        f"{node.metadata.get('start_time')}-{node.metadata.get('end_time')}]\n{node.get_text()}"
        for node in nodes
    )
    return f"{SPOILER_SAFE_PROMPT}\n\n资料：\n{context or '无可用资料'}\n\n问题：{question}\n\n回答："


def summarize_collection_rows(
    *,
    collection: str,
    chroma_dir: Path,
    ids: list[Any],
    metadatas: list[dict[str, Any] | None],
) -> dict[str, Any]:
    episodes: dict[str, dict[str, Any]] = {}
    for metadata in metadatas:
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
        source_type = str(metadata.get("source_type"))
        item["source_types"][source_type] = item["source_types"].get(source_type, 0) + 1

    return {
        "collection": collection,
        "chroma_dir": str(chroma_dir),
        "total_documents": len(ids),
        "episodes": list(episodes.values()),
    }


def _require_api_key(settings: Settings) -> None:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required before running story Q&A with a real vector store.")


def _use_pysqlite3() -> None:
    try:
        import pysqlite3
        import sys

        sys.modules["sqlite3"] = pysqlite3
    except Exception:
        pass


def _uses_local_hash_embedding(settings: Settings) -> bool:
    return settings.openai_embedding_model.lower() in {"local-hash", "local_hash"}


def _hash_embedding(text: str, dimensions: int = 384) -> list[float]:
    tokens = re.findall(r"[\w]+", text.lower(), flags=re.UNICODE)
    tokens.extend(char for char in text if "\u4e00" <= char <= "\u9fff")
    if not tokens:
        tokens = [text[:32] or "empty"]

    vector = [0.0] * dimensions
    for token in tokens:
        index = hash(token) % dimensions
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _complete_with_openai_chat(settings: Settings, prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_api_base)
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def _configure_llama_index(settings: Settings) -> None:
    from llama_index.core import Settings as LlamaSettings
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.llms.openai import OpenAI

    LlamaSettings.llm = OpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        api_base=settings.openai_api_base,
    )
    LlamaSettings.embed_model = OpenAIEmbedding(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
        api_base=settings.openai_api_base,
    )


def _get_chroma_collection(settings: Settings):
    _use_pysqlite3()
    import chromadb

    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return client.get_or_create_collection(settings.chroma_collection)


def _get_index(settings: Settings):
    _use_pysqlite3()
    from llama_index.core import StorageContext, VectorStoreIndex
    from llama_index.vector_stores.chroma import ChromaVectorStore

    _configure_llama_index(settings)
    vector_store = ChromaVectorStore(chroma_collection=_get_chroma_collection(settings))
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)


def _document_id(doc: StoryQaDocument, index: int) -> str:
    metadata = doc.metadata
    return "::".join(
        [
            str(metadata.get("series_id")),
            f"E{metadata.get('episode')}",
            str(metadata.get("source_type")),
            str(metadata.get("source_file")),
            str(metadata.get("chunk_index", metadata.get("frame_number", index))),
        ]
    )


def _ingest_with_local_hash(settings: Settings, documents: list[StoryQaDocument]) -> None:
    collection = _get_chroma_collection(settings)
    collection.upsert(
        ids=[_document_id(doc, index) for index, doc in enumerate(documents)],
        documents=[doc.text for doc in documents],
        metadatas=[doc.metadata for doc in documents],
        embeddings=[_hash_embedding(doc.text) for doc in documents],
    )


def ingest(input_dir: Path, series_id: str, episode: int) -> dict[str, Any]:
    _use_pysqlite3()
    from llama_index.core import Document

    settings = get_settings()
    _require_api_key(settings)
    documents = build_documents(input_dir, series_id, episode)
    if not documents:
        raise RuntimeError(f"No ingestible documents found in {input_dir}")

    if _uses_local_hash_embedding(settings):
        _ingest_with_local_hash(settings, documents)
    else:
        index = _get_index(settings)
        for doc in documents:
            index.insert(Document(text=doc.text, metadata=doc.metadata))

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


def ask(question: str, series_id: str, current_episode: int, current_time: float) -> dict[str, Any]:
    _use_pysqlite3()
    from llama_index.core import Settings as LlamaSettings
    from llama_index.core.vector_stores import ExactMatchFilter, MetadataFilters

    settings = get_settings()
    _require_api_key(settings)
    if _uses_local_hash_embedding(settings):
        collection = _get_chroma_collection(settings)
        results = collection.query(
            query_embeddings=[_hash_embedding(question)],
            n_results=settings.similarity_top_k * 5,
            where={"series_id": series_id},
            include=["documents", "metadatas", "distances"],
        )
        documents = results.get("documents") or [[]]
        metadatas = results.get("metadatas") or [[]]
        distances = results.get("distances") or [[]]
        nodes = [
            ChromaQueryNode(
                text=str(text),
                metadata=dict(metadata or {}),
                score=1.0 / (1.0 + float(distance or 0.0)),
            )
            for text, metadata, distance in zip(documents[0], metadatas[0], distances[0])
        ]
        nodes = [node for node in nodes if is_visible(node, current_episode, current_time)][: settings.similarity_top_k]
        response = _complete_with_openai_chat(settings, build_prompt(question, nodes))
        return {
            "answer": response,
            "sources": [
                {
                    "score": float(node.score or 0.0),
                    "text": node.get_text(),
                    "metadata": dict(node.metadata),
                }
                for node in nodes
            ],
        }

    index = _get_index(settings)
    retriever = index.as_retriever(
        similarity_top_k=settings.similarity_top_k * 5,
        filters=MetadataFilters(filters=[ExactMatchFilter(key="series_id", value=series_id)]),
    )
    nodes = [
        node
        for node in retriever.retrieve(question)
        if is_visible(node, current_episode, current_time)
    ][: settings.similarity_top_k]
    response = str(LlamaSettings.llm.complete(build_prompt(question, nodes)))

    return {
        "answer": response,
        "sources": [
            {
                "score": float(node.score or 0.0),
                "text": node.get_text(),
                "metadata": dict(node.metadata),
            }
            for node in nodes
        ],
    }


def collections() -> dict[str, Any]:
    settings = get_settings()
    collection = _get_chroma_collection(settings)
    rows = collection.get(include=["metadatas"])
    return summarize_collection_rows(
        collection=settings.chroma_collection,
        chroma_dir=settings.chroma_dir,
        ids=rows.get("ids") or [],
        metadatas=rows.get("metadatas") or [],
    )
