from __future__ import annotations

import json
import math
from pathlib import Path
import queue
import re
import asyncio
import threading
from typing import Any, Iterable, Protocol

from services.api.config import Settings, get_settings


_LIGHTRAG_LOOP: asyncio.AbstractEventLoop | None = None
_LIGHTRAG_LOOP_LOCK = threading.Lock()
_LIGHTRAG_CACHE_LOCK = threading.Lock()
_LIGHTRAG_RAG: Any | None = None
_LIGHTRAG_RAG_KEY: tuple[Any, ...] | None = None
_REFERENCE_HEADING_RE = re.compile(r"(?im)^\s*#{1,6}\s*references\s*$")
_REFERENCE_LIST_RE = re.compile(r"(?im)^\s*[-*]\s*\[\d+\].*$")
_CITATION_RE = re.compile(r"\[\d+\]")
_THINK_BLOCK_RE = re.compile(r"(?is)<think>.*?</think>")


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


def _uses_lightrag(settings: Settings) -> bool:
    return settings.story_qa_backend == "lightrag"


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


def _get_lightrag_loop() -> asyncio.AbstractEventLoop:
    global _LIGHTRAG_LOOP
    with _LIGHTRAG_LOOP_LOCK:
        if _LIGHTRAG_LOOP is None or _LIGHTRAG_LOOP.is_closed():
            loop = asyncio.new_event_loop()
            thread = threading.Thread(target=loop.run_forever, name="lightrag-event-loop", daemon=True)
            thread.start()
            _LIGHTRAG_LOOP = loop
        return _LIGHTRAG_LOOP


def _run_lightrag_async(coro):
    future = asyncio.run_coroutine_threadsafe(coro, _get_lightrag_loop())
    return future.result()


def _clean_lightrag_text(text: str) -> str:
    text = _THINK_BLOCK_RE.sub("", text)
    cleaned = _REFERENCE_HEADING_RE.split(text, maxsplit=1)[0]
    cleaned = _REFERENCE_LIST_RE.sub("", cleaned)
    cleaned = _CITATION_RE.sub("", cleaned)
    return cleaned.strip()


def _clean_lightrag_stream_chunk(chunk: str, in_think: bool = False) -> tuple[str, bool, bool]:
    output = ""
    remaining = chunk
    while remaining:
        if in_think:
            end = remaining.lower().find("</think>")
            if end < 0:
                return output, False, True
            remaining = remaining[end + len("</think>") :]
            in_think = False
            continue
        start = remaining.lower().find("<think>")
        if start < 0:
            output += remaining
            break
        output += remaining[:start]
        remaining = remaining[start + len("<think>") :]
        in_think = True

    match = _REFERENCE_HEADING_RE.search(chunk)
    should_stop = match is not None
    if match:
        output = output[: match.start()]
    return _CITATION_RE.sub("", output), should_stop, in_think


def _lightrag_cache_key(settings: Settings) -> tuple[Any, ...]:
    return (
        str(settings.lightrag_working_dir.resolve()),
        settings.openai_model,
        settings.openai_api_base,
        settings.openai_api_key,
        settings.lightrag_embedding_model,
        settings.lightrag_embedding_dim,
        settings.lightrag_embedding_api_base,
        settings.lightrag_embedding_api_key,
        settings.lightrag_embedding_send_dim,
        settings.lightrag_top_k,
        settings.lightrag_chunk_top_k,
        settings.lightrag_cosine_threshold,
        settings.lightrag_max_entity_tokens,
        settings.lightrag_max_relation_tokens,
        settings.lightrag_max_total_tokens,
    )


async def _get_lightrag_async(settings: Settings):
    global _LIGHTRAG_RAG, _LIGHTRAG_RAG_KEY

    if not settings.lightrag_working_dir.exists():
        raise RuntimeError(f"LIGHTRAG_WORKING_DIR does not exist: {settings.lightrag_working_dir}")

    cache_key = _lightrag_cache_key(settings)
    if _LIGHTRAG_RAG is not None and _LIGHTRAG_RAG_KEY == cache_key:
        return _LIGHTRAG_RAG

    from lightrag import LightRAG
    from lightrag.llm.openai import openai_complete_if_cache, openai_embed
    from lightrag.utils import EmbeddingFunc

    async def embedding_func(texts: list[str]):
        return await openai_embed.func(
            texts,
            model=settings.lightrag_embedding_model,
            base_url=settings.lightrag_embedding_api_base,
            api_key=settings.lightrag_embedding_api_key,
            embedding_dim=settings.lightrag_embedding_dim if settings.lightrag_embedding_send_dim else None,
        )

    async def llm_model_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, Any]] | None = None,
        keyword_extraction: bool = False,
        **kwargs: Any,
    ) -> str:
        try:
            return await openai_complete_if_cache(
                settings.openai_model,
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages or [],
                keyword_extraction=False,
                base_url=settings.openai_api_base,
                api_key=settings.openai_api_key,
                **kwargs,
            )
        except Exception:
            if keyword_extraction:
                return await openai_complete_if_cache(
                    settings.openai_model,
                    prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages or [],
                    keyword_extraction=False,
                    base_url=settings.openai_api_base,
                    api_key=settings.openai_api_key,
                    **kwargs,
                )
            raise

    rag = LightRAG(
        working_dir=str(settings.lightrag_working_dir),
        embedding_func=EmbeddingFunc(
            embedding_dim=settings.lightrag_embedding_dim,
            max_token_size=8192,
            send_dimensions=settings.lightrag_embedding_send_dim,
            model_name=settings.lightrag_embedding_model,
            func=embedding_func,
        ),
        llm_model_func=llm_model_func,
        top_k=settings.lightrag_top_k,
        chunk_top_k=settings.lightrag_chunk_top_k,
        cosine_threshold=settings.lightrag_cosine_threshold,
        cosine_better_than_threshold=settings.lightrag_cosine_threshold,
        max_entity_tokens=settings.lightrag_max_entity_tokens,
        max_relation_tokens=settings.lightrag_max_relation_tokens,
        max_total_tokens=settings.lightrag_max_total_tokens,
    )
    await rag.initialize_storages()
    _LIGHTRAG_RAG = rag
    _LIGHTRAG_RAG_KEY = cache_key
    return rag


def _ensure_lightrag(settings: Settings) -> None:
    with _LIGHTRAG_CACHE_LOCK:
        _run_lightrag_async(_get_lightrag_async(settings))


async def _ask_lightrag_async(settings: Settings, question: str, current_episode: int) -> dict[str, Any]:
    from lightrag import QueryParam

    rag = await _get_lightrag_async(settings)
    answer = await rag.aquery(
        question,
        param=QueryParam(
            mode=settings.lightrag_query_mode,
            enable_rerank=settings.lightrag_enable_rerank,
            top_k=settings.lightrag_top_k,
            chunk_top_k=settings.lightrag_chunk_top_k,
            max_entity_tokens=settings.lightrag_max_entity_tokens,
            max_relation_tokens=settings.lightrag_max_relation_tokens,
            max_total_tokens=settings.lightrag_max_total_tokens,
            response_type=settings.lightrag_response_type,
            include_references=False,
            current_chapter_id=int(current_episode),
        ),
    )

    return {"answer": _clean_lightrag_text(str(answer)), "sources": []}


async def _ask_lightrag_stream_async(
    settings: Settings,
    question: str,
    current_episode: int,
    output: queue.Queue[str | Exception | None],
) -> None:
    from lightrag import QueryParam

    try:
        rag = await _get_lightrag_async(settings)
        answer = await rag.aquery(
            question,
            param=QueryParam(
                mode=settings.lightrag_query_mode,
                enable_rerank=settings.lightrag_enable_rerank,
                top_k=settings.lightrag_top_k,
                chunk_top_k=settings.lightrag_chunk_top_k,
                max_entity_tokens=settings.lightrag_max_entity_tokens,
                max_relation_tokens=settings.lightrag_max_relation_tokens,
                max_total_tokens=settings.lightrag_max_total_tokens,
                response_type=settings.lightrag_response_type,
                include_references=False,
                stream=True,
                current_chapter_id=int(current_episode),
            ),
        )
        if hasattr(answer, "__aiter__"):
            in_think = False
            async for chunk in answer:
                cleaned_chunk, should_stop, in_think = _clean_lightrag_stream_chunk(str(chunk), in_think)
                if cleaned_chunk:
                    output.put(cleaned_chunk)
                if should_stop:
                    break
        else:
            cleaned = _clean_lightrag_text(str(answer))
            if cleaned:
                output.put(cleaned)
    except Exception as exc:
        output.put(exc)
    finally:
        output.put(None)


def _ask_lightrag(settings: Settings, question: str, current_episode: int) -> dict[str, Any]:
    _require_api_key(settings)
    _ensure_lightrag(settings)
    return _run_lightrag_async(_ask_lightrag_async(settings, question, current_episode))


def _ask_lightrag_stream(settings: Settings, question: str, current_episode: int) -> Iterable[str]:
    _require_api_key(settings)
    _ensure_lightrag(settings)
    output: queue.Queue[str | Exception | None] = queue.Queue()
    future = asyncio.run_coroutine_threadsafe(
        _ask_lightrag_stream_async(settings, question, current_episode, output),
        _get_lightrag_loop(),
    )
    while True:
        item = output.get()
        if item is None:
            break
        if isinstance(item, Exception):
            raise item
        yield item
    future.result()


def warmup_lightrag_backend() -> None:
    settings = get_settings()
    if not _uses_lightrag(settings):
        return
    _require_api_key(settings)
    _ensure_lightrag(settings)


def reset_lightrag_cache_for_tests() -> None:
    global _LIGHTRAG_RAG, _LIGHTRAG_RAG_KEY
    with _LIGHTRAG_CACHE_LOCK:
        _LIGHTRAG_RAG = None
        _LIGHTRAG_RAG_KEY = None


def _ingest_lightrag(settings: Settings, input_dir: Path, series_id: str, episode: int) -> dict[str, Any]:
    if not settings.lightrag_working_dir.exists():
        raise RuntimeError(f"LIGHTRAG_WORKING_DIR does not exist: {settings.lightrag_working_dir}")
    return {
        "input_dir": str(input_dir.resolve()),
        "series_id": series_id,
        "episode": episode,
        "documents": 0,
        "by_type": {"prebuilt_lightrag": 0},
        "chroma_dir": str(settings.lightrag_working_dir),
        "collection": "lightrag_prebuilt",
    }


def _collections_lightrag(settings: Settings) -> dict[str, Any]:
    if not settings.lightrag_working_dir.exists():
        raise RuntimeError(f"LIGHTRAG_WORKING_DIR does not exist: {settings.lightrag_working_dir}")

    status_path = settings.lightrag_working_dir / "kv_store_doc_status.json"
    statuses = _read_json(status_path)
    episodes = []
    if statuses:
        episodes.append(
            {
                "series_id": "prebuilt-lightrag",
                "episode": None,
                "documents": len(statuses),
                "source_types": {"prebuilt_lightrag": len(statuses)},
            }
        )
    return {
        "collection": "lightrag_prebuilt",
        "chroma_dir": str(settings.lightrag_working_dir),
        "total_documents": len(statuses),
        "episodes": episodes,
    }


def ingest(input_dir: Path, series_id: str, episode: int) -> dict[str, Any]:
    settings = get_settings()
    if _uses_lightrag(settings):
        return _ingest_lightrag(settings, input_dir, series_id, episode)

    _use_pysqlite3()
    from llama_index.core import Document

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
    settings = get_settings()
    if _uses_lightrag(settings):
        return _ask_lightrag(settings, question, current_episode)

    _use_pysqlite3()
    from llama_index.core import Settings as LlamaSettings
    from llama_index.core.vector_stores import ExactMatchFilter, MetadataFilters

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


def ask_stream(question: str, series_id: str, current_episode: int, current_time: float) -> Iterable[str]:
    settings = get_settings()
    if _uses_lightrag(settings):
        return _ask_lightrag_stream(settings, question, current_episode)

    answer = ask(question, series_id, current_episode, current_time)["answer"]
    return iter([str(answer)])


def collections() -> dict[str, Any]:
    settings = get_settings()
    if _uses_lightrag(settings):
        return _collections_lightrag(settings)

    collection = _get_chroma_collection(settings)
    rows = collection.get(include=["metadatas"])
    return summarize_collection_rows(
        collection=settings.chroma_collection,
        chroma_dir=settings.chroma_dir,
        ids=rows.get("ids") or [],
        metadatas=rows.get("metadatas") or [],
    )
