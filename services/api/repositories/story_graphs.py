from __future__ import annotations

from collections.abc import Iterable
import re
from pathlib import Path
from typing import Any

import networkx as nx

from ..config import get_settings
from .admin_content import list_series


GRAPH_FILE_NAME = "graph_chunk_entity_relation.graphml"
SAFE_SERIES_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _resolve_graph_path(series_id: str) -> Path:
    if not SAFE_SERIES_ID_RE.fullmatch(series_id):
        raise FileNotFoundError(series_id)
    settings = get_settings()
    root = settings.lightrag_working_root.resolve()
    graph_path = (root / series_id / "lightrag" / GRAPH_FILE_NAME).resolve()
    if not graph_path.is_relative_to(root):
        raise FileNotFoundError(series_id)
    return graph_path


def _read_graph(series_id: str) -> nx.Graph:
    graph_path = _resolve_graph_path(series_id)
    if not graph_path.is_file():
        raise FileNotFoundError(series_id)
    return nx.read_graphml(graph_path)


def _chapter_ids(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    text = str(value).strip()
    if not text:
        return []
    numbers = re.findall(r"\d+", text)
    return sorted({int(number) for number in numbers})


def _node_payload(graph: nx.Graph, node_id: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node_id,
        "label": str(data.get("entity_id") or node_id),
        "entity_type": str(data.get("entity_type") or "unknown"),
        "description": str(data.get("description") or ""),
        "degree": int(graph.degree(node_id)),
        "chapter_ids": _chapter_ids(data.get("chapter_ids") or data.get("chapter_id")),
    }


def _edge_payload(index: int, source: str, target: str, data: dict[str, Any]) -> dict[str, Any]:
    weight = data.get("weight")
    return {
        "id": str(data.get("id") or f"{source}->{target}#{index}"),
        "source": source,
        "target": target,
        "keywords": str(data.get("keywords") or ""),
        "description": str(data.get("description") or ""),
        "weight": float(weight) if weight is not None else None,
        "chapter_ids": _chapter_ids(data.get("chapter_ids") or data.get("chapter_id")),
    }


def _matches_query(node: dict[str, Any], query: str) -> bool:
    keyword = query.strip().lower()
    if not keyword:
        return True
    return keyword in f"{node['label']} {node['entity_type']} {node['description']}".lower()


def _limit_nodes(nodes: Iterable[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return sorted(nodes, key=lambda node: (-int(node["degree"]), str(node["label"])))[:limit]


def list_story_graphs() -> list[dict[str, Any]]:
    series_by_id = {item["series_id"]: item for item in list_series()}
    root = get_settings().lightrag_working_root.resolve()
    items: list[dict[str, Any]] = []
    if not root.is_dir():
        return []

    for graph_path in sorted(root.glob(f"*/lightrag/{GRAPH_FILE_NAME}")):
        series_id = graph_path.parent.parent.name
        if not SAFE_SERIES_ID_RE.fullmatch(series_id):
            continue
        try:
            graph = nx.read_graphml(graph_path)
        except Exception:
            items.append(
                {
                    "series_id": series_id,
                    "series_name": (series_by_id.get(series_id) or {}).get("series_name"),
                    "node_count": 0,
                    "edge_count": 0,
                    "available": False,
                }
            )
            continue
        items.append(
            {
                "series_id": series_id,
                "series_name": (series_by_id.get(series_id) or {}).get("series_name"),
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
                "available": True,
            }
        )
    return items


def get_story_graph(series_id: str, query: str = "", limit: int = 300) -> dict[str, Any] | None:
    try:
        graph = _read_graph(series_id)
    except FileNotFoundError:
        return None

    all_nodes = [_node_payload(graph, str(node_id), dict(data)) for node_id, data in graph.nodes(data=True)]
    matched_nodes = [node for node in all_nodes if _matches_query(node, query)]
    selected_nodes = _limit_nodes(matched_nodes, max(1, min(limit, 1000)))
    selected_ids = {node["id"] for node in selected_nodes}

    if query.strip():
        for source, target in graph.edges(selected_ids):
            selected_ids.add(str(source))
            selected_ids.add(str(target))
        selected_nodes = [node for node in all_nodes if node["id"] in selected_ids]

    edges: list[dict[str, Any]] = []
    for index, (source, target, data) in enumerate(graph.edges(data=True), start=1):
        source_id = str(source)
        target_id = str(target)
        if source_id in selected_ids and target_id in selected_ids:
            edges.append(_edge_payload(index, source_id, target_id, dict(data)))

    return {
        "series_id": series_id,
        "node_count": len(selected_nodes),
        "edge_count": len(edges),
        "total_node_count": graph.number_of_nodes(),
        "total_edge_count": graph.number_of_edges(),
        "nodes": selected_nodes,
        "edges": edges,
    }
