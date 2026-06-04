from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.client.factory import build_llm_client
from scripts.algorithm.common import (
    DEFAULT_DATA_ROOT,
    discover_episodes,
    extract_video_metadata,
    load_source_payload,
    now_iso,
    write_failure_diagnostics,
)
from scripts.run_expression_trigger_detection_batch import expression_triggers_to_highlight_assets


DEFAULT_OUTPUT_ROOT = Path("output/workflow_expression_trigger")


def _format_optional_number(value: Any, *, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value}{suffix}"


def print_workflow_progress(event: str, payload: dict[str, Any]) -> None:
    video_id = str(payload.get("video_id") or "unknown")
    if event == "preprocess_subtitles_loaded":
        print(
            f"[{video_id}] preprocess_subtitles_loaded: "
            f"subtitles={payload.get('subtitle_segment_count', 0)} "
            f"subtitle_duration={_format_optional_number(payload.get('subtitle_duration_sec'), suffix='s')}"
        )
        return
    if event == "preprocess_duration_probed":
        print(
            f"[{video_id}] preprocess_duration_probed: "
            f"subtitle_duration={_format_optional_number(payload.get('subtitle_duration_sec'), suffix='s')} "
            f"video_duration={_format_optional_number(payload.get('video_duration_sec'), suffix='s')} "
            f"duration={_format_optional_number(payload.get('duration_sec'), suffix='s')}"
        )
        return
    if event == "preprocess_visual_windows_start":
        print(
            f"[{video_id}] preprocess_visual_windows_start: "
            f"duration={_format_optional_number(payload.get('duration_sec'), suffix='s')} "
            f"subtitles={payload.get('subtitle_segment_count', 0)} "
            f"visual_window_sec={payload.get('visual_candidate_window_sec')}s"
        )
        return
    if event == "preprocess_visual_windows_done":
        print(
            f"[{video_id}] preprocess_visual_windows_done: "
            f"visual_windows={payload.get('visual_window_count', 0)} "
            f"elapsed={_format_optional_number(payload.get('elapsed_sec'), suffix='s')}"
        )
        return
    if event == "preprocess_candidate_frames_built":
        print(
            f"[{video_id}] preprocess_candidate_frames_built: "
            f"candidate_frames={payload.get('candidate_frame_count', 0)} "
            f"sample_interval={payload.get('sample_interval_sec')}s "
            f"visual_interval={payload.get('visual_window_sample_interval_sec')}s"
        )
        return
    if event == "prepared":
        print(
            f"[{video_id}] prepared: "
            f"duration={_format_optional_number(payload.get('duration_sec'), suffix='s')} "
            f"subtitles={payload.get('subtitle_segment_count', 0)} "
            f"visual_windows={payload.get('visual_window_count', 0)} "
            f"candidate_frames={payload.get('candidate_frame_count', 0)} "
            f"sample_interval={payload.get('sample_interval_sec')}s "
            f"visual_window_sec={payload.get('visual_candidate_window_sec')}s "
            f"visual_interval={payload.get('visual_window_sample_interval_sec')}s"
        )
        visual_windows = payload.get("visual_candidate_windows")
        if isinstance(visual_windows, list):
            for index, window in enumerate(visual_windows, start=1):
                if not isinstance(window, dict):
                    continue
                try:
                    start_time = float(window["start_time"])
                    end_time = float(window["end_time"])
                except (KeyError, TypeError, ValueError):
                    continue
                reason = str(window.get("reason") or "")
                print(f"[{video_id}] visual_window[{index:02d}]: {start_time:.3f}-{end_time:.3f} reason={reason}")
        return
    if event == "candidate_frames_extracted":
        print(
            f"[{video_id}] candidate_frames_extracted: "
            f"requested={payload.get('requested_frame_count', 0)} "
            f"extracted={payload.get('extracted_frame_count', 0)} "
            f"images={payload.get('image_count', 0)}"
        )
        return
    if event == "candidate_generation_start":
        print(
            f"[{video_id}] candidate_generation_start: "
            f"frames={payload.get('frame_count', 0)} "
            f"images={payload.get('image_count', 0)} "
            f"max_tokens={payload.get('max_tokens')}"
        )
        return
    if event == "candidate_generation_done":
        print(
            f"[{video_id}] candidate_generation_done: "
            f"candidates={payload.get('candidate_count', 0)} "
            f"elapsed={_format_optional_number(payload.get('elapsed_sec'), suffix='s')} "
            f"tokens={_format_optional_number(payload.get('total_tokens'))}"
        )
        return
    if event == "filter_frames_extracted":
        print(
            f"[{video_id}] filter_frames_extracted: "
            f"requested={payload.get('filter_frame_count', 0)} "
            f"extracted={payload.get('extracted_frame_count', 0)} "
            f"images={payload.get('image_count', 0)}"
        )
        return
    if event == "candidate_filtering_start":
        print(
            f"[{video_id}] candidate_filtering_start: "
            f"candidates={payload.get('candidate_count', 0)} "
            f"frames={payload.get('frame_count', 0)} "
            f"images={payload.get('image_count', 0)} "
            f"max_tokens={payload.get('max_tokens')}"
        )
        return
    if event == "candidate_filtering_done":
        print(
            f"[{video_id}] candidate_filtering_done: "
            f"decisions={payload.get('candidate_decision_count', 0)} "
            f"parsed_triggers={payload.get('parsed_trigger_count', 0)} "
            f"triggers={payload.get('trigger_count', 0)} "
            f"elapsed={_format_optional_number(payload.get('elapsed_sec'), suffix='s')} "
            f"tokens={_format_optional_number(payload.get('total_tokens'))}"
        )
        return
    if event == "completed":
        print(
            f"[{video_id}] completed: "
            f"candidates={payload.get('candidate_count', 0)} "
            f"decisions={payload.get('candidate_decision_count', 0)} "
            f"triggers={payload.get('trigger_count', 0)} "
            f"resonance_cues={payload.get('resonance_cue_count', 0)}"
        )
        return
    print(f"[{video_id}] {event}: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}")


def build_pipeline(
    *,
    env_path: Path,
    sample_interval_sec: float,
    max_frames: int | None,
    frame_max_height: int,
    visual_candidate_window_sec: float,
    visual_window_sample_interval_sec: float,
    visual_window_max_frames: int | None,
    filter_frame_interval_sec: float,
    filter_candidate_context_sec: float,
    filter_max_frames: int | None,
    final_same_expression_gap_sec: float,
    final_min_intensity: float,
    final_min_confidence: float,
    final_max_triggers: int | None,
    candidate_max_output_tokens: int,
    filter_max_output_tokens: int,
):
    from pipelines.workflow_expression_trigger_detection import WorkflowExpressionTriggerPipeline

    return WorkflowExpressionTriggerPipeline(
        llm_client=build_llm_client(env_path=env_path),
        sample_interval_sec=sample_interval_sec,
        max_frames=max_frames,
        frame_max_height=frame_max_height,
        visual_candidate_window_sec=visual_candidate_window_sec,
        visual_window_sample_interval_sec=visual_window_sample_interval_sec,
        visual_window_max_frames=visual_window_max_frames,
        filter_frame_interval_sec=filter_frame_interval_sec,
        filter_candidate_context_sec=filter_candidate_context_sec,
        filter_max_frames=filter_max_frames,
        final_same_expression_gap_sec=final_same_expression_gap_sec,
        final_min_intensity=final_min_intensity,
        final_min_confidence=final_min_confidence,
        final_max_triggers=final_max_triggers,
        candidate_max_output_tokens=candidate_max_output_tokens,
        filter_max_output_tokens=filter_max_output_tokens,
        progress_callback=print_workflow_progress,
    )


def write_workflow_episode_output(
    *,
    episode: Any,
    output_root: Path,
    expression_candidates: list[dict[str, Any]],
    candidate_decisions: list[dict[str, Any]],
    expression_triggers: list[dict[str, Any]],
    resonance_cues: list[dict[str, Any]],
    llm_call: dict[str, Any] | None = None,
) -> Path:
    output_dir = output_root / episode.video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "video_id": episode.video_id,
        "video_path": str(episode.video_path),
        "source_json_path": str(episode.source_json_path) if episode.source_json_path else None,
        "subtitle_path": str(episode.subtitle_path),
        "created_at": now_iso(),
        "pipeline_type": "workflow_expression_trigger",
        "llm_call": llm_call or {},
        "expression_candidates": expression_candidates,
        "candidate_decisions": candidate_decisions,
        "expression_triggers": expression_triggers,
        "resonance_cues": resonance_cues,
        "highlight_assets": expression_triggers_to_highlight_assets(expression_triggers),
    }
    output_path = output_dir / "highlight_recognition.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch run two-stage workflow Expression Trigger Detection over DataForAlgorithm episodes.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--series-id",
        nargs="+",
        action="append",
        help="Only process selected series directories, for example --series-id beiwang nanian_dongzhi.",
    )
    parser.add_argument(
        "--episode-id",
        nargs="+",
        action="append",
        help="Only process selected episode directories across selected series, for example --episode-id ep01 ep02.",
    )
    parser.add_argument(
        "--video-id",
        nargs="+",
        action="append",
        help="Only process exact video ids, for example --video-id beiwang_ep01 nanian_dongzhi_ep02.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Process at most N episodes. Default: all.")
    parser.add_argument("--force", action="store_true", help="Regenerate outputs that already exist.")
    parser.add_argument("--sample-interval-sec", type=float, default=10.0)
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--frame-max-height", type=int, default=512)
    parser.add_argument("--visual-candidate-window-sec", type=float, default=10.0)
    parser.add_argument("--visual-window-sample-interval-sec", type=float, default=1.0)
    parser.add_argument("--visual-window-max-frames", type=int, default=80)
    parser.add_argument("--filter-frame-interval-sec", type=float, default=2.0)
    parser.add_argument("--filter-candidate-context-sec", type=float, default=2.0)
    parser.add_argument("--filter-max-frames", type=int, default=100)
    parser.add_argument("--final-same-expression-gap-sec", type=float, default=30.0)
    parser.add_argument("--final-min-intensity", type=float, default=0.6)
    parser.add_argument("--final-min-confidence", type=float, default=0.72)
    parser.add_argument("--final-max-triggers", type=int, default=4)
    parser.add_argument("--candidate-max-output-tokens", type=int, default=2400)
    parser.add_argument("--filter-max-output-tokens", type=int, default=2400)
    return parser


def main(argv: Sequence[str] | None = None, *, pipeline: Any | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    series_ids = [series_id for group in (args.series_id or []) for series_id in group]
    episode_ids = [episode_id for group in (args.episode_id or []) for episode_id in group]
    video_ids = [video_id for group in (args.video_id or []) for video_id in group]
    episodes = discover_episodes(
        data_root=args.data_root,
        series_ids=series_ids,
        episode_ids=episode_ids,
        video_ids=video_ids,
        limit=args.limit,
    )
    active_pipeline = pipeline or build_pipeline(
        env_path=args.env_file,
        sample_interval_sec=args.sample_interval_sec,
        max_frames=args.max_frames,
        frame_max_height=args.frame_max_height,
        visual_candidate_window_sec=args.visual_candidate_window_sec,
        visual_window_sample_interval_sec=args.visual_window_sample_interval_sec,
        visual_window_max_frames=args.visual_window_max_frames,
        filter_frame_interval_sec=args.filter_frame_interval_sec,
        filter_candidate_context_sec=args.filter_candidate_context_sec,
        filter_max_frames=args.filter_max_frames,
        final_same_expression_gap_sec=args.final_same_expression_gap_sec,
        final_min_intensity=args.final_min_intensity,
        final_min_confidence=args.final_min_confidence,
        final_max_triggers=args.final_max_triggers,
        candidate_max_output_tokens=args.candidate_max_output_tokens,
        filter_max_output_tokens=args.filter_max_output_tokens,
    )

    processed = 0
    skipped = 0
    failed: list[tuple[str, str]] = []
    for episode in episodes:
        output_path = args.output_root / episode.video_id / "highlight_recognition.json"
        if output_path.exists() and not args.force:
            skipped += 1
            print(f"SKIP {episode.video_id}: existing {output_path}")
            continue
        print(f"RUN  {episode.video_id}")
        source_payload = load_source_payload(episode.source_json_path)
        metadata = extract_video_metadata(source_payload)
        llm_call: dict[str, Any] = {}
        try:
            result = active_pipeline.run(
                video_id=episode.video_id,
                video_file_path=episode.video_path,
                subtitle_file_path=episode.subtitle_path,
                metadata=metadata,
            )
            llm_call = dict(result.llm_calls) if isinstance(result.llm_calls, dict) else {}
            written_path = write_workflow_episode_output(
                episode=episode,
                output_root=args.output_root,
                expression_candidates=result.expression_candidates,
                candidate_decisions=result.candidate_decisions,
                expression_triggers=result.expression_triggers,
                resonance_cues=result.resonance_cues,
                llm_call=llm_call,
            )
        except Exception as exc:  # noqa: BLE001 - batch jobs should continue and report all episode failures.
            raw_llm_call = getattr(active_pipeline, "last_llm_call", {})
            llm_call = dict(raw_llm_call) if isinstance(raw_llm_call, dict) else llm_call
            failed.append((episode.video_id, str(exc)))
            diagnostic_path = write_failure_diagnostics(
                episode=episode,
                output_root=args.output_root,
                error=exc,
                metadata=metadata,
                danmaku_items=[],
                llm_call=llm_call,
            )
            print(f"FAIL {episode.video_id}: {exc} (diagnostics: {diagnostic_path})", file=sys.stderr)
            continue
        processed += 1
        print(f"WROTE {written_path}")

    print(f"Done. discovered={len(episodes)} processed={processed} skipped={skipped} failed={len(failed)}")
    if failed:
        for video_id, error in failed:
            print(f"- {video_id}: {error}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
