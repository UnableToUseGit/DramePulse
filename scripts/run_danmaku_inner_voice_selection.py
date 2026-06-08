from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.client.factory import build_llm_client
from pipelines.danmaku_inner_voice_selection import (
    load_semantic_clusters_payload,
    select_inner_voice_candidates_from_semantic_clusters,
    write_inner_voice_selection_output,
)

DEFAULT_SEMANTIC_CLUSTERS_PATH = Path("output/danmaku_exploration/semantic_clusters_beiwang_ep01_hdbscan.json")
DEFAULT_OUTPUT_PATH = Path("output/danmaku_exploration/inner_voice_selection_beiwang_ep01.json")
DEFAULT_ASSETS_ROOT = Path("/Users/qinminghao/Desktop/ByteDance/DataForAlgorithm")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select inner voice danmaku candidates from semantic clusters with LLM.")
    parser.add_argument("--semantic-clusters-path", type=Path, default=DEFAULT_SEMANTIC_CLUSTERS_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--assets-root", type=Path, default=DEFAULT_ASSETS_ROOT)
    parser.add_argument("--transcription-path", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--series-id", default="beiwang")
    parser.add_argument("--episode-id", default="ep01")
    parser.add_argument("--top-cluster-count", type=int, default=50)
    parser.add_argument("--representative-comment-count", type=int, default=3)
    parser.add_argument("--example-count", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=4000)
    return parser


def resolve_transcription_path(
    *,
    assets_root: Path,
    series_id: str,
    episode_id: str,
    explicit_path: Path | None = None,
) -> Path:
    if explicit_path is not None:
        return explicit_path
    return assets_root / series_id / episode_id / "video.transcription.json"


def print_inner_voice_selection_progress(event: str, payload: dict[str, Any]) -> None:
    if event == "prepared":
        print(
            f"[{payload.get('video_id')}] prepared: "
            f"utterances={payload.get('utterance_count', 0)} "
            f"clusters={payload.get('cluster_count', 0)} "
            f"top_cluster_count={payload.get('top_cluster_count', 0)}",
            flush=True,
        )
        return
    if event == "llm_start":
        print(
            f"[{payload.get('video_id')}] llm_start: "
            f"clusters={payload.get('cluster_count', 0)} "
            f"max_tokens={payload.get('max_tokens', 0)}",
            flush=True,
        )
        return
    if event == "llm_done":
        token_count = payload.get("total_tokens")
        token_text = token_count if token_count is not None else "n/a"
        print(
            f"[{payload.get('video_id')}] llm_done: "
            f"candidates={payload.get('candidate_count', 0)} "
            f"filtered={payload.get('filtered_count', 0)} "
            f"tokens={token_text}",
            flush=True,
        )
        return
    if event == "completed":
        print(
            f"[{payload.get('video_id')}] completed: "
            f"candidates={payload.get('candidate_count', 0)} "
            f"filtered={payload.get('filtered_count', 0)}",
            flush=True,
        )
        return
    print(f"{event}: {payload}", flush=True)


def main(argv: Sequence[str] | None = None, *, llm_client: Any | None = None) -> int:
    args = build_parser().parse_args(argv)
    transcription_path = resolve_transcription_path(
        assets_root=args.assets_root,
        series_id=args.series_id,
        episode_id=args.episode_id,
        explicit_path=args.transcription_path,
    )
    active_client = llm_client or build_llm_client(env_path=args.env_file)
    semantic_payload = load_semantic_clusters_payload(args.semantic_clusters_path)
    result = select_inner_voice_candidates_from_semantic_clusters(
        semantic_payload,
        transcription_path=transcription_path,
        llm_client=active_client,
        top_cluster_count=args.top_cluster_count,
        representative_comment_count=args.representative_comment_count,
        example_count=args.example_count,
        max_tokens=args.max_tokens,
        progress_callback=print_inner_voice_selection_progress,
    )
    write_inner_voice_selection_output(output_path=args.output_path, payload=result)
    print(
        "Wrote inner voice selection: "
        f"candidates={result['candidateCount']} "
        f"output={args.output_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
