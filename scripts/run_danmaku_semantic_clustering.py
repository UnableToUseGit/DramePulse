from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.client.embedding import CachedEmbeddingClient, OpenAICompatibleEmbeddingClient, OpenRouterEmbeddingClient
from pipelines.danmaku_semantic_clustering import cluster_danmaku_semantics_from_csv, write_semantic_clusters_output
from scripts.transcription.env import load_dotenv_values

DEFAULT_CSV_PATH = Path("data/圈选剧前5集弹幕.csv")
DEFAULT_OUTPUT_PATH = Path("output/danmaku_exploration/semantic_clusters.json")
DEFAULT_EMBEDDING_CACHE_PATH = Path("output/danmaku_exploration/embedding_cache.sqlite")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cluster full-episode danmaku semantics with embeddings.")
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--series-id", help="Only process one series id, for example beiwang.")
    parser.add_argument("--episode-id", help="Only process one episode id, for example ep01.")
    parser.add_argument("--cluster-method", choices=["hdbscan", "connected_components"], default="hdbscan")
    parser.add_argument("--similarity-threshold", type=float, default=0.82)
    parser.add_argument("--min-cluster-comment-count", type=int, default=3)
    parser.add_argument("--peak-window-sec", type=float, default=8.0)
    parser.add_argument("--max-clusters-per-episode", type=int, default=20)
    parser.add_argument("--top-k-clusters", type=int, default=3)
    parser.add_argument("--representative-comment-count", type=int, default=5)
    parser.add_argument("--hdbscan-min-cluster-size", type=int, default=5)
    parser.add_argument("--hdbscan-min-samples", type=int, default=3)
    parser.add_argument("--hdbscan-cluster-selection-method", choices=["eom", "leaf"], default="eom")
    parser.add_argument("--embedding-base-url", help="OpenAI-compatible embeddings endpoint base URL.")
    parser.add_argument("--embedding-api-key", help="Embeddings API key.")
    parser.add_argument("--embedding-model", help="Embedding model name, for example baai/bge-m3.")
    parser.add_argument("--embedding-batch-size", type=int, default=128)
    parser.add_argument("--embedding-cache-path", type=Path, default=DEFAULT_EMBEDDING_CACHE_PATH)
    parser.add_argument("--no-embedding-cache", action="store_true")
    return parser


def _config_value(dotenv_values: dict[str, str], explicit_value: str | None, *keys: str) -> str | None:
    if explicit_value:
        return explicit_value
    for key in keys:
        value = dotenv_values.get(key)
        if value:
            return value
    return None


def _openrouter_embeddings_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/embeddings"):
        return normalized
    return f"{normalized}/embeddings"


def build_embedding_client_from_args(args: argparse.Namespace):
    dotenv_values = load_dotenv_values(args.env_file)
    api_key = _config_value(dotenv_values, args.embedding_api_key, "EMBEDDING_API_KEY", "OPENROUTER_API_KEY", "API_KEY")
    base_url = _config_value(dotenv_values, args.embedding_base_url, "EMBEDDING_BASE_URL", "BASE_URL")
    model_name = _config_value(dotenv_values, args.embedding_model, "EMBEDDING_MODEL", "MODEL") or "baai/bge-m3"
    if base_url and "openrouter.ai" in base_url:
        client = OpenRouterEmbeddingClient(
            api_key=api_key,
            url=_openrouter_embeddings_url(base_url),
            model_name=model_name,
            batch_size=args.embedding_batch_size,
            site_url=_config_value(dotenv_values, None, "OPENROUTER_SITE_URL", "EMBEDDING_SITE_URL"),
            site_name=_config_value(dotenv_values, None, "OPENROUTER_SITE_NAME", "EMBEDDING_SITE_NAME"),
            progress_callback=print_embedding_progress,
        )
    else:
        client = OpenAICompatibleEmbeddingClient(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            batch_size=args.embedding_batch_size,
        )
    if args.no_embedding_cache:
        return client
    return CachedEmbeddingClient(
        inner_client=client,
        cache_path=args.embedding_cache_path,
        model_name=model_name,
    )


def print_embedding_progress(event: str, payload: dict[str, Any]) -> None:
    if event == "embedding_batch":
        token_count = payload.get("total_tokens")
        token_text = f" tokens={token_count}" if token_count is not None else ""
        print(
            "embedding_batch: "
            f"{payload.get('batch_index', 0)}/{payload.get('batch_count', 0)} "
            f"size={payload.get('batch_size', 0)}"
            f"{token_text}",
            flush=True,
        )
        return
    print(f"{event}: {payload}", flush=True)


def print_semantic_clustering_progress(event: str, payload: dict[str, Any]) -> None:
    if event == "prepared":
        print(f"prepared: episodes={payload.get('episode_count', 0)} comments={payload.get('filtered_comment_count', 0)}", flush=True)
        return
    if event == "episode_start":
        print(
            f"[{payload.get('video_id')}] episode_start: "
            f"comments={payload.get('comment_count', 0)} "
            f"expression_groups={payload.get('expression_group_count', 0)}",
            flush=True,
        )
        return
    if event == "embedding_start":
        print(
            f"[{payload.get('video_id')}] embedding_start: "
            f"expression_groups={payload.get('expression_group_count', 0)}",
            flush=True,
        )
        return
    if event == "embedding_done":
        diagnostics = payload.get("embedding_diagnostics", {})
        usage = diagnostics.get("usage", {}) if isinstance(diagnostics, dict) else {}
        token_count = usage.get("total_tokens") if isinstance(usage, dict) else None
        token_text = f" tokens={token_count}" if token_count is not None else ""
        print(f"[{payload.get('video_id')}] embedding_done: vectors={payload.get('vector_count', 0)}{token_text}", flush=True)
        return
    if event == "clustering_start":
        method = payload.get("cluster_method")
        if method == "hdbscan":
            detail = (
                f"method=hdbscan "
                f"min_cluster_size={payload.get('hdbscan_min_cluster_size')} "
                f"min_samples={payload.get('hdbscan_min_samples')} "
                f"top_k={payload.get('top_k_clusters')}"
            )
        else:
            detail = f"method=connected_components threshold={payload.get('similarity_threshold')}"
        print(
            f"[{payload.get('video_id')}] clustering_start: "
            f"vectors={payload.get('vector_count', 0)} "
            f"{detail}",
            flush=True,
        )
        return
    if event == "clustering_done":
        print(f"[{payload.get('video_id')}] clustering_done: clusters={payload.get('cluster_count', 0)}", flush=True)
        return
    if event == "completed":
        print(f"completed: episodes={payload.get('episode_count', 0)} clusters={payload.get('cluster_count', 0)}", flush=True)
        return
    print(f"{event}: {payload}", flush=True)


def main(argv: Sequence[str] | None = None, *, embedding_client: Any | None = None) -> int:
    args = build_parser().parse_args(argv)
    active_client = embedding_client or build_embedding_client_from_args(args)
    payload = cluster_danmaku_semantics_from_csv(
        args.csv_path,
        embedding_client=active_client,
        series_id=args.series_id,
        episode_id=args.episode_id,
        cluster_method=args.cluster_method,
        similarity_threshold=args.similarity_threshold,
        min_cluster_comment_count=args.min_cluster_comment_count,
        peak_window_sec=args.peak_window_sec,
        max_clusters_per_episode=args.max_clusters_per_episode,
        top_k_clusters=args.top_k_clusters,
        representative_comment_count=args.representative_comment_count,
        hdbscan_min_cluster_size=args.hdbscan_min_cluster_size,
        hdbscan_min_samples=args.hdbscan_min_samples,
        hdbscan_cluster_selection_method=args.hdbscan_cluster_selection_method,
        progress_callback=print_semantic_clustering_progress,
    )
    write_semantic_clusters_output(output_path=args.output_path, payload=payload)
    print(
        "Wrote danmaku semantic clusters: "
        f"episodes={payload['episodeCount']} "
        f"clusters={payload['clusterCount']} "
        f"output={args.output_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
