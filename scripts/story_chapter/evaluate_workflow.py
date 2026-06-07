from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import statistics
from typing import Any, Sequence


DEFAULT_GOLD_ROOT = Path("data/annotations/story_chapter_gold")
DEFAULT_PREDICTION_ROOT = Path("output/story_chapter_workflow_validation/manual_check")
DEFAULT_REPORT_PATH = DEFAULT_PREDICTION_ROOT / "story_chapter_gold_evaluation.json"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return payload


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_gold_boundaries(gold: dict[str, Any]) -> list[float]:
    raw_boundaries = gold.get("boundaries") if isinstance(gold.get("boundaries"), list) else []
    times: list[float] = []
    for boundary in raw_boundaries:
        if not isinstance(boundary, dict):
            continue
        time = _safe_float(boundary.get("time"))
        if time is not None:
            times.append(_round_time(time))
    return sorted(set(times))


def _extract_story_chapters(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_chapters = payload.get("story_chapters")
    if not isinstance(raw_chapters, list):
        raw_chapters = payload.get("chapters")
    chapters: list[dict[str, Any]] = []
    if not isinstance(raw_chapters, list):
        return chapters
    for chapter in raw_chapters:
        if not isinstance(chapter, dict):
            continue
        start_time = _safe_float(chapter.get("start_time"))
        end_time = _safe_float(chapter.get("end_time"))
        if start_time is None or end_time is None or end_time <= start_time:
            continue
        chapters.append({**chapter, "start_time": _round_time(start_time), "end_time": _round_time(end_time)})
    return sorted(chapters, key=lambda chapter: float(chapter["start_time"]))


def _extract_internal_boundaries_from_chapters(chapters: list[dict[str, Any]]) -> list[float]:
    if len(chapters) <= 1:
        return []
    return [_round_time(float(chapter["end_time"])) for chapter in chapters[:-1]]


def _prediction_path_for(prediction_root: Path, video_id: str) -> Path:
    return prediction_root / video_id / "story_chapters.json"


def _safe_divide(numerator: float, denominator: float, *, empty_value: float = 0.0) -> float:
    if denominator == 0:
        return empty_value
    return numerator / denominator


def _match_boundaries(
    *,
    gold_boundaries: list[float],
    predicted_boundaries: list[float],
    tolerance_seconds: float,
) -> tuple[list[dict[str, float]], list[float], list[float]]:
    unmatched_predictions = set(range(len(predicted_boundaries)))
    matches: list[dict[str, float]] = []
    unmatched_gold: list[float] = []

    for gold_time in gold_boundaries:
        best_index: int | None = None
        best_error: float | None = None
        for pred_index in sorted(unmatched_predictions):
            error = abs(predicted_boundaries[pred_index] - gold_time)
            if best_error is None or error < best_error:
                best_index = pred_index
                best_error = error
        if best_index is None or best_error is None or best_error > tolerance_seconds:
            unmatched_gold.append(gold_time)
            continue
        unmatched_predictions.remove(best_index)
        predicted_time = predicted_boundaries[best_index]
        matches.append(
            {
                "gold_time": gold_time,
                "predicted_time": predicted_time,
                "error_seconds": _round_time(predicted_time - gold_time),
                "abs_error_seconds": _round_time(best_error),
            }
        )

    unmatched_predicted = [predicted_boundaries[index] for index in sorted(unmatched_predictions)]
    return matches, unmatched_gold, unmatched_predicted


def evaluate_episode(
    *,
    gold_path: Path,
    prediction_path: Path,
    tolerance_seconds: float,
) -> dict[str, Any]:
    gold = _safe_read_json(gold_path)
    video_id = str(gold.get("video_id") or gold_path.name.removesuffix(".annotation.json"))
    gold_boundaries = _extract_gold_boundaries(gold)
    gold_chapters = _extract_story_chapters(gold)

    if not prediction_path.exists():
        return {
            "video_id": video_id,
            "status": "missing_prediction",
            "gold_path": str(gold_path),
            "prediction_path": str(prediction_path),
            "gold_boundary_count": len(gold_boundaries),
            "predicted_boundary_count": 0,
            "matched_boundary_count": 0,
            "false_positive_count": 0,
            "false_negative_count": len(gold_boundaries),
            "matched_boundaries": [],
            "unmatched_gold_boundaries": gold_boundaries,
            "unmatched_predicted_boundaries": [],
        }

    prediction = _safe_read_json(prediction_path)
    predicted_chapters = _extract_story_chapters(prediction)
    predicted_boundaries = _extract_internal_boundaries_from_chapters(predicted_chapters)
    matches, unmatched_gold, unmatched_predicted = _match_boundaries(
        gold_boundaries=gold_boundaries,
        predicted_boundaries=predicted_boundaries,
        tolerance_seconds=tolerance_seconds,
    )
    abs_errors = [match["abs_error_seconds"] for match in matches]
    matched_count = len(matches)
    precision = _safe_divide(matched_count, len(predicted_boundaries), empty_value=1.0 if not gold_boundaries else 0.0)
    recall = _safe_divide(matched_count, len(gold_boundaries), empty_value=1.0)
    f1 = _safe_divide(2 * precision * recall, precision + recall)

    return {
        "video_id": video_id,
        "status": "evaluated",
        "gold_path": str(gold_path),
        "prediction_path": str(prediction_path),
        "tolerance_seconds": tolerance_seconds,
        "gold_chapter_count": len(gold_chapters),
        "predicted_chapter_count": len(predicted_chapters),
        "chapter_count_delta": len(predicted_chapters) - len(gold_chapters),
        "gold_boundary_count": len(gold_boundaries),
        "predicted_boundary_count": len(predicted_boundaries),
        "boundary_count_delta": len(predicted_boundaries) - len(gold_boundaries),
        "matched_boundary_count": matched_count,
        "false_positive_count": len(unmatched_predicted),
        "false_negative_count": len(unmatched_gold),
        "over_segmentation_count": max(0, len(predicted_boundaries) - len(gold_boundaries)),
        "under_segmentation_count": max(0, len(gold_boundaries) - len(predicted_boundaries)),
        "boundary_precision": precision,
        "boundary_recall": recall,
        "boundary_f1": f1,
        "mean_abs_boundary_error_seconds": statistics.mean(abs_errors) if abs_errors else None,
        "median_abs_boundary_error_seconds": statistics.median(abs_errors) if abs_errors else None,
        "max_abs_boundary_error_seconds": max(abs_errors) if abs_errors else None,
        "gold_boundaries": gold_boundaries,
        "predicted_boundaries": predicted_boundaries,
        "matched_boundaries": matches,
        "unmatched_gold_boundaries": unmatched_gold,
        "unmatched_predicted_boundaries": unmatched_predicted,
    }


def _discover_gold_paths(gold_root: Path, video_ids: Sequence[str] | None = None) -> list[Path]:
    allowed = set(video_ids or [])
    paths = sorted(gold_root.glob("*.annotation.json"))
    if not allowed:
        return paths
    return [path for path in paths if path.name.removesuffix(".annotation.json") in allowed]


def build_summary(
    *,
    episode_results: list[dict[str, Any]],
    gold_root: Path,
    prediction_root: Path,
    tolerance_seconds: float,
) -> dict[str, Any]:
    evaluated = [result for result in episode_results if result.get("status") == "evaluated"]
    total_matched = sum(int(result["matched_boundary_count"]) for result in episode_results)
    total_predicted = sum(int(result["predicted_boundary_count"]) for result in episode_results)
    total_gold = sum(int(result["gold_boundary_count"]) for result in episode_results)
    micro_precision = _safe_divide(total_matched, total_predicted, empty_value=1.0 if total_gold == 0 else 0.0)
    micro_recall = _safe_divide(total_matched, total_gold, empty_value=1.0)
    micro_f1 = _safe_divide(2 * micro_precision * micro_recall, micro_precision + micro_recall)
    all_abs_errors = [
        match["abs_error_seconds"]
        for result in evaluated
        for match in result.get("matched_boundaries", [])
        if isinstance(match, dict) and isinstance(match.get("abs_error_seconds"), int | float)
    ]
    return {
        "created_at": _now_iso(),
        "gold_root": str(gold_root),
        "prediction_root": str(prediction_root),
        "tolerance_seconds": tolerance_seconds,
        "total_episodes": len(episode_results),
        "evaluated_episodes": len(evaluated),
        "missing_prediction_episodes": len(episode_results) - len(evaluated),
        "micro_boundary_precision": micro_precision,
        "micro_boundary_recall": micro_recall,
        "micro_boundary_f1": micro_f1,
        "macro_boundary_precision": statistics.mean(result["boundary_precision"] for result in evaluated) if evaluated else None,
        "macro_boundary_recall": statistics.mean(result["boundary_recall"] for result in evaluated) if evaluated else None,
        "macro_boundary_f1": statistics.mean(result["boundary_f1"] for result in evaluated) if evaluated else None,
        "mean_abs_boundary_error_seconds": statistics.mean(all_abs_errors) if all_abs_errors else None,
        "median_abs_boundary_error_seconds": statistics.median(all_abs_errors) if all_abs_errors else None,
        "total_gold_boundaries": total_gold,
        "total_predicted_boundaries": total_predicted,
        "total_matched_boundaries": total_matched,
        "total_false_positives": sum(int(result["false_positive_count"]) for result in episode_results),
        "total_false_negatives": sum(int(result["false_negative_count"]) for result in episode_results),
        "episodes": episode_results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Story Chapter workflow output against gold boundary annotations.")
    parser.add_argument("--gold-root", type=Path, default=DEFAULT_GOLD_ROOT)
    parser.add_argument("--prediction-root", type=Path, default=DEFAULT_PREDICTION_ROOT)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--tolerance-seconds", type=float, default=5.0)
    parser.add_argument("--video-id", action="append", default=[], help="Evaluate one video_id. May be repeated.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    gold_paths = _discover_gold_paths(args.gold_root, args.video_id)
    episode_results: list[dict[str, Any]] = []
    for gold_path in gold_paths:
        video_id = gold_path.name.removesuffix(".annotation.json")
        result = evaluate_episode(
            gold_path=gold_path,
            prediction_path=_prediction_path_for(args.prediction_root, video_id),
            tolerance_seconds=args.tolerance_seconds,
        )
        episode_results.append(result)
        print(
            f"{result['video_id']}: status={result['status']} "
            f"matched={result['matched_boundary_count']}/{result['gold_boundary_count']} "
            f"pred={result['predicted_boundary_count']} fp={result['false_positive_count']} "
            f"fn={result['false_negative_count']}",
            flush=True,
        )

    summary = build_summary(
        episode_results=episode_results,
        gold_root=args.gold_root,
        prediction_root=args.prediction_root,
        tolerance_seconds=args.tolerance_seconds,
    )
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "Summary: "
        f"episodes={summary['evaluated_episodes']}/{summary['total_episodes']} "
        f"micro_f1={summary['micro_boundary_f1']:.3f} "
        f"macro_f1={summary['macro_boundary_f1'] if summary['macro_boundary_f1'] is not None else 'NA'}",
        flush=True,
    )
    print(f"Wrote evaluation report: {args.report_path}", flush=True)
    return 1 if summary["missing_prediction_episodes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
