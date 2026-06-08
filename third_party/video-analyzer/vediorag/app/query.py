from typing import Any

from llama_index.core.schema import NodeWithScore
from llama_index.core.vector_stores import ExactMatchFilter, MetadataFilters

from .config import get_settings
from .store import configure_llama_index, get_index


SPOILER_SAFE_PROMPT = """你是短剧情节问答助手。
只能基于下方检索到的、用户当前观看进度内的资料回答。
不要使用后续剧情、常识猜测或未提供资料补全答案。
如果当前进度内无法确认答案，请明确说“当前观看进度内无法确认”。
回答使用简体中文，并尽量引用集数、时间点或资料类型。
"""


def build_series_filter(series_id: str) -> MetadataFilters:
    return MetadataFilters(filters=[ExactMatchFilter(key="series_id", value=series_id)])


def is_visible(node: NodeWithScore, current_episode: int, current_time: float) -> bool:
    metadata = node.metadata or {}
    episode = int(metadata.get("episode") or 0)
    end_time = float(metadata.get("end_time") or 0.0)
    return episode < current_episode or (episode == current_episode and end_time <= float(current_time))


def ask(question: str, series_id: str, current_episode: int, current_time: float) -> dict[str, Any]:
    settings = get_settings(require_api_key=True)
    index = get_index(settings)
    retriever = index.as_retriever(
        similarity_top_k=settings.similarity_top_k * 5,
        filters=build_series_filter(series_id),
    )
    nodes = [
        node
        for node in retriever.retrieve(question)
        if is_visible(node, current_episode, current_time)
    ][: settings.similarity_top_k]
    context = "\n\n".join(
        f"[{node.metadata.get('source_type')} E{node.metadata.get('episode')} "
        f"{node.metadata.get('start_time')}-{node.metadata.get('end_time')}]\n{node.get_text()}"
        for node in nodes
    )

    prompt = f"{SPOILER_SAFE_PROMPT}\n\n资料：\n{context or '无可用资料'}\n\n问题：{question}\n\n回答："
    response = settings_response(prompt)

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


def settings_response(prompt: str) -> str:
    from llama_index.core import Settings as LlamaSettings

    settings = get_settings(require_api_key=True)
    configure_llama_index(settings)
    return str(LlamaSettings.llm.complete(prompt))
