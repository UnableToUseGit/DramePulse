from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from ..config import get_settings
from .admin_content import list_series


GRAPH_FILE_NAME = "graph_chunk_entity_relation.graphml"
SAFE_SERIES_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class StoryGraph:
    nodes: dict[str, dict[str, Any]]
    edges: list[tuple[str, str, dict[str, Any]]]

    def degree(self, node_id: str) -> int:
        return sum(1 for source, target, _ in self.edges if source == node_id or target == node_id)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


def _resolve_graph_path(series_id: str) -> Path:
    if not SAFE_SERIES_ID_RE.fullmatch(series_id):
        raise FileNotFoundError(series_id)
    settings = get_settings()
    root = settings.lightrag_working_root.resolve()
    graph_path = (root / series_id / "lightrag" / GRAPH_FILE_NAME).resolve()
    if not graph_path.is_relative_to(root):
        raise FileNotFoundError(series_id)
    return graph_path


def _read_graph(series_id: str) -> StoryGraph:
    graph_path = _resolve_graph_path(series_id)
    if not graph_path.is_file():
        raise FileNotFoundError(series_id)
    return _parse_graphml(graph_path)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_graphml(path: Path) -> StoryGraph:
    root = ET.parse(path).getroot()
    key_names = {
        str(item.attrib.get("id")): str(item.attrib.get("attr.name") or item.attrib.get("id"))
        for item in root.iter()
        if _local_name(item.tag) == "key" and item.attrib.get("id")
    }
    graph_element = next((item for item in root.iter() if _local_name(item.tag) == "graph"), None)
    if graph_element is None:
        return StoryGraph(nodes={}, edges=[])

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[tuple[str, str, dict[str, Any]]] = []
    for item in graph_element:
        tag = _local_name(item.tag)
        if tag == "node":
            node_id = str(item.attrib.get("id") or "").strip()
            if node_id:
                nodes[node_id] = _graphml_data(item, key_names)
        elif tag == "edge":
            source = str(item.attrib.get("source") or "").strip()
            target = str(item.attrib.get("target") or "").strip()
            if source and target:
                edges.append((source, target, _graphml_data(item, key_names)))
    return StoryGraph(nodes=nodes, edges=edges)


def _graphml_data(element: ET.Element, key_names: dict[str, str]) -> dict[str, str]:
    data: dict[str, str] = {}
    for child in element:
        if _local_name(child.tag) != "data":
            continue
        key = str(child.attrib.get("key") or "")
        name = key_names.get(key, key)
        data[name] = child.text or ""
    return data


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


def _node_payload(graph: StoryGraph, node_id: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node_id,
        "label": str(data.get("entity_id") or node_id),
        "entity_type": str(data.get("entity_type") or "unknown"),
        "description": str(data.get("description") or ""),
        "degree": graph.degree(node_id),
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
            graph = _parse_graphml(graph_path)
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
                "node_count": graph.node_count,
                "edge_count": graph.edge_count,
                "available": True,
            }
        )
    return items


def get_story_graph(series_id: str, query: str = "", limit: int = 300) -> dict[str, Any] | None:
    try:
        graph = _read_graph(series_id)
    except FileNotFoundError:
        return None

    all_nodes = [_node_payload(graph, node_id, data) for node_id, data in graph.nodes.items()]
    matched_nodes = [node for node in all_nodes if _matches_query(node, query)]
    selected_nodes = _limit_nodes(matched_nodes, max(1, min(limit, 1000)))
    selected_ids = {node["id"] for node in selected_nodes}

    if query.strip():
        for source, target, _ in graph.edges:
            if source in selected_ids or target in selected_ids:
                selected_ids.add(source)
                selected_ids.add(target)
        selected_nodes = [node for node in all_nodes if node["id"] in selected_ids]

    edges: list[dict[str, Any]] = []
    for index, (source, target, data) in enumerate(graph.edges, start=1):
        if source in selected_ids and target in selected_ids:
            edges.append(_edge_payload(index, source, target, data))

    return {
        "series_id": series_id,
        "node_count": len(selected_nodes),
        "edge_count": len(edges),
        "total_node_count": graph.node_count,
        "total_edge_count": graph.edge_count,
        "nodes": selected_nodes,
        "edges": edges,
    }
