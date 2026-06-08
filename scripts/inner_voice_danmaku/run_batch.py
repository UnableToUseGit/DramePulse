from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipelines.client.factory import build_llm_client
from scripts.inner_voice_danmaku import build_interaction_plan, select_candidates, semantic_clustering

DEFAULT_CSV_PATH = semantic_clustering.DEFAULT_CSV_PATH
DEFAULT_OUTPUT_DIR = Path("output/danmaku_exploration")
DEFAULT_ASSETS_ROOT = select_candidates.DEFAULT_ASSETS_ROOT
DEFAULT_EMBEDDING_CACHE_PATH = semantic_clustering.DEFAULT_EMBEDDING_CACHE_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run inner voice danmaku assets for multiple episodes.")
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--assets-root", type=Path, default=DEFAULT_ASSETS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--series-id", required=True)
    parser.add_argument("--episode-ids", nargs="+", required=True)

    parser.add_argument("--cluster-method", choices=["hdbscan", "connected_components"], default="hdbscan")
    parser.add_argument("--similarity-threshold", type=float, default=0.82)
    parser.add_argument("--min-cluster-comment-count", type=int, default=3)
    parser.add_argument("--peak-window-sec", type=float, default=8.0)
    parser.add_argument("--max-clusters-per-episode", type=int, default=20)
    parser.add_argument("--top-k-clusters", type=int, default=3)
    parser.add_argument("--semantic-representative-comment-count", type=int, default=5)
    parser.add_argument("--hdbscan-min-cluster-size", type=int, default=5)
    parser.add_argument("--hdbscan-min-samples", type=int, default=3)
    parser.add_argument("--hdbscan-cluster-selection-method", choices=["eom", "leaf"], default="eom")

    parser.add_argument("--embedding-base-url")
    parser.add_argument("--embedding-api-key")
    parser.add_argument("--embedding-model")
    parser.add_argument("--embedding-batch-size", type=int, default=128)
    parser.add_argument("--embedding-cache-path", type=Path, default=DEFAULT_EMBEDDING_CACHE_PATH)
    parser.add_argument("--no-embedding-cache", action="store_true")

    parser.add_argument("--top-cluster-count", type=int, default=50)
    parser.add_argument("--selection-representative-comment-count", type=int, default=3)
    parser.add_argument("--example-count", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=4000)

    parser.add_argument("--min-duration-sec", type=float, default=5.0)
    parser.add_argument("--max-duration-sec", type=float, default=8.0)
    return parser


def _semantic_output_path(output_dir: Path, series_id: str, episode_id: str) -> Path:
    return output_dir / f"semantic_clusters_{series_id}_{episode_id}.json"


def _selection_output_path(output_dir: Path, series_id: str, episode_id: str) -> Path:
    return output_dir / f"inner_voice_selection_{series_id}_{episode_id}.json"


def _plan_output_path(output_dir: Path, series_id: str, episode_id: str) -> Path:
    return output_dir / f"interaction_plan_{series_id}_{episode_id}.json"


def _run_episode(
    *,
    args: argparse.Namespace,
    episode_id: str,
    embedding_client: Any,
    llm_client: Any,
) -> None:
    semantic_path = _semantic_output_path(args.output_dir, args.series_id, episode_id)
    selection_path = _selection_output_path(args.output_dir, args.series_id, episode_id)
    plan_path = _plan_output_path(args.output_dir, args.series_id, episode_id)
    print(f"[{args.series_id}_{episode_id}] batch_start", flush=True)
    semantic_clustering.main(
        [
            "--csv-path",
            str(args.csv_path),
            "--output-path",
            str(semantic_path),
            "--env-file",
            str(args.env_file),
            "--series-id",
            args.series_id,
            "--episode-id",
            episode_id,
            "--cluster-method",
            args.cluster_method,
            "--similarity-threshold",
            str(args.similarity_threshold),
            "--min-cluster-comment-count",
            str(args.min_cluster_comment_count),
            "--peak-window-sec",
            str(args.peak_window_sec),
            "--max-clusters-per-episode",
            str(args.max_clusters_per_episode),
            "--top-k-clusters",
            str(args.top_k_clusters),
            "--representative-comment-count",
            str(args.semantic_representative_comment_count),
            "--hdbscan-min-cluster-size",
            str(args.hdbscan_min_cluster_size),
            "--hdbscan-min-samples",
            str(args.hdbscan_min_samples),
            "--hdbscan-cluster-selection-method",
            args.hdbscan_cluster_selection_method,
            "--embedding-batch-size",
            str(args.embedding_batch_size),
            "--embedding-cache-path",
            str(args.embedding_cache_path),
            *(["--embedding-base-url", args.embedding_base_url] if args.embedding_base_url else []),
            *(["--embedding-api-key", args.embedding_api_key] if args.embedding_api_key else []),
            *(["--embedding-model", args.embedding_model] if args.embedding_model else []),
            *(["--no-embedding-cache"] if args.no_embedding_cache else []),
        ],
        embedding_client=embedding_client,
    )
    select_candidates.main(
        [
            "--semantic-clusters-path",
            str(semantic_path),
            "--output-path",
            str(selection_path),
            "--assets-root",
            str(args.assets_root),
            "--env-file",
            str(args.env_file),
            "--series-id",
            args.series_id,
            "--episode-id",
            episode_id,
            "--top-cluster-count",
            str(args.top_cluster_count),
            "--representative-comment-count",
            str(args.selection_representative_comment_count),
            "--example-count",
            str(args.example_count),
            "--max-tokens",
            str(args.max_tokens),
        ],
        llm_client=llm_client,
    )
    build_interaction_plan.main(
        [
            "--selection-path",
            str(selection_path),
            "--output-path",
            str(plan_path),
            "--series-id",
            args.series_id,
            "--episode-id",
            episode_id,
            "--min-duration-sec",
            str(args.min_duration_sec),
            "--max-duration-sec",
            str(args.max_duration_sec),
        ]
    )
    print(f"[{args.series_id}_{episode_id}] batch_done output={plan_path}", flush=True)


def main(
    argv: Sequence[str] | None = None,
    *,
    embedding_client: Any | None = None,
    llm_client: Any | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    active_embedding_client = embedding_client or semantic_clustering.build_embedding_client_from_args(args)
    active_llm_client = llm_client or build_llm_client(env_path=args.env_file)
    for episode_id in args.episode_ids:
        _run_episode(
            args=args,
            episode_id=episode_id,
            embedding_client=active_embedding_client,
            llm_client=active_llm_client,
        )
    print(f"batch_completed: episodes={len(args.episode_ids)} output_dir={args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
