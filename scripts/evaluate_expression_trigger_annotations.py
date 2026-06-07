from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.expression_trigger_detection import normalize_plot_primary_expression


DEFAULT_ANNOTATION_DIR = Path("data/annotations/expression_trigger_gold")
DEFAULT_ALGORITHM_OUTPUT_ROOT = Path("output/expression_trigger")
DEFAULT_REPORT_PATH = Path("output/expression_trigger_annotation_eval/report.json")
ALGORITHM_OUTPUT_FILENAMES = ("expression_triggers.json", "highlight_recognition.json")
SUPPORTED_EVAL_EXPRESSIONS = {"爽点", "甜点", "泪点", "笑点"}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _round_metric(value: float) -> float:
    return round(float(value), 6)


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _time_value(item: dict[str, Any]) -> float | None:
    for key in ("trigger_time", "payoff_time", "cue_time"):
        try:
            value = float(item[key])
        except (KeyError, TypeError, ValueError):
            continue
        return value
    return None


def _normalized_expression(value: Any) -> str:
    return normalize_plot_primary_expression(value)


def _payoff_window(item: dict[str, Any]) -> dict[str, float] | None:
    window = item.get("payoff_window")
    if not isinstance(window, dict):
        return None
    try:
        start_time = float(window["start_time"])
        end_time = float(window["end_time"])
    except (KeyError, TypeError, ValueError):
        return None
    if start_time < 0 or end_time < start_time:
        return None
    return {"start_time": _round_time(start_time), "end_time": _round_time(end_time)}


def _valid_gold_annotations(payload: Any) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(payload, dict):
        return "", []
    video_id = str(payload.get("video_id") or "").strip()
    annotations = payload.get("annotations")
    if not isinstance(annotations, list):
        return video_id, []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(annotations, start=1):
        if not isinstance(item, dict):
            continue
        payoff_time = _time_value(item)
        if payoff_time is None:
            continue
        primary_expression = normalize_plot_primary_expression(item.get("primary_expression"))
        if payoff_time < 0 or not primary_expression:
            continue
        payoff_window = _payoff_window(item)
        normalized.append(
            {
                "annotation_id": str(item.get("annotation_id") or f"gold_{video_id}_{index:03d}"),
                "payoff_time": _round_time(payoff_time),
                "cue_time": _round_time(payoff_time),
                "payoff_window": payoff_window,
                "primary_expression": primary_expression,
                "reason": str(item.get("reason") or "").strip(),
            }
        )
    return video_id, sorted(normalized, key=lambda item: (float(item["cue_time"]), str(item["annotation_id"])))


def _valid_predictions(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    raw_triggers = payload.get("expression_triggers")
    if not isinstance(raw_triggers, list):
        return []
    predictions: list[dict[str, Any]] = []
    for index, item in enumerate(raw_triggers, start=1):
        if not isinstance(item, dict):
            continue
        payoff_time = _time_value(item)
        if payoff_time is None:
            continue
        primary_expression = normalize_plot_primary_expression(
            item.get("expression_type") or item.get("primary_expression") or item.get("emotion")
        )
        if payoff_time < 0 or not primary_expression:
            continue
        predictions.append(
            {
                "trigger_id": str(item.get("trigger_id") or f"pred_{index:03d}"),
                "payoff_time": _round_time(payoff_time),
                "cue_time": _round_time(payoff_time),
                "primary_expression": primary_expression,
                "source_type": str(item.get("source_type") or ""),
                "summary": str(item.get("summary") or ""),
                "reason": str(item.get("reason") or ""),
                "confidence": item.get("confidence"),
            }
        )
    return sorted(predictions, key=lambda item: (float(item["cue_time"]), str(item["trigger_id"])))


def evaluate_episode(
    *,
    video_id: str,
    gold_annotations: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    tolerance_sec: float,
    missing_algorithm_output: bool = False,
) -> dict[str, Any]:
    unmatched_prediction_indexes = set(range(len(predictions)))
    matches: list[dict[str, Any]] = []
    missed: list[dict[str, Any]] = []

    for annotation in gold_annotations:
        best_index: int | None = None
        best_delta: float | None = None
        best_matched_by = ""
        for prediction_index in unmatched_prediction_indexes:
            prediction = predictions[prediction_index]
            prediction_time_value = _time_value(prediction)
            annotation_time_value = _time_value(annotation)
            if prediction_time_value is None or annotation_time_value is None:
                continue
            prediction_time = float(prediction_time_value)
            annotation_time = float(annotation_time_value)
            delta = abs(prediction_time - annotation_time)
            matched_by = "tolerance"
            window = annotation.get("payoff_window")
            if isinstance(window, dict):
                try:
                    start_time = float(window["start_time"])
                    end_time = float(window["end_time"])
                except (KeyError, TypeError, ValueError):
                    start_time = 0.0
                    end_time = -1.0
                if start_time <= prediction_time <= end_time:
                    matched_by = "payoff_window"
                elif delta > tolerance_sec:
                    continue
            elif delta > tolerance_sec:
                continue
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_index = prediction_index
                best_matched_by = matched_by
        if best_index is None or best_delta is None:
            missed.append(annotation)
            continue

        unmatched_prediction_indexes.remove(best_index)
        prediction = predictions[best_index]
        prediction_time = float(_time_value(prediction) or 0.0)
        annotation_time = float(_time_value(annotation) or 0.0)
        annotation_expression = _normalized_expression(annotation.get("primary_expression"))
        prediction_expression = _normalized_expression(
            prediction.get("primary_expression") or prediction.get("expression_type") or prediction.get("emotion")
        )
        unsupported_gold_expression = annotation_expression not in SUPPORTED_EVAL_EXPRESSIONS
        expression_match = (not unsupported_gold_expression) and prediction_expression == annotation_expression
        annotation_for_report = {
            **annotation,
            "payoff_time": _round_time(annotation_time),
            "cue_time": _round_time(annotation_time),
            "primary_expression": annotation_expression,
        }
        prediction_for_report = {
            **prediction,
            "payoff_time": _round_time(prediction_time),
            "cue_time": _round_time(prediction_time),
            "primary_expression": prediction_expression,
        }
        matches.append(
            {
                "annotation": annotation_for_report,
                "prediction": prediction_for_report,
                "time_delta_sec": _round_time(best_delta),
                "matched_by": best_matched_by,
                "expression_match": expression_match,
                "unsupported_gold_expression": unsupported_gold_expression,
            }
        )

    false_positives = [predictions[index] for index in sorted(unmatched_prediction_indexes)]
    matched_count = len(matches)
    gold_count = len(gold_annotations)
    prediction_count = len(predictions)
    expression_correct_count = sum(1 for match in matches if match["expression_match"])
    unsupported_gold_count = sum(
        1 for annotation in gold_annotations if _normalized_expression(annotation.get("primary_expression")) not in SUPPORTED_EVAL_EXPRESSIONS
    )
    supported_matched_count = sum(1 for match in matches if not match["unsupported_gold_expression"])

    return {
        "video_id": video_id,
        "missing_algorithm_output": missing_algorithm_output,
        "gold_count": gold_count,
        "prediction_count": prediction_count,
        "matched_count": matched_count,
        "expression_correct_count": expression_correct_count,
        "unsupported_gold_count": unsupported_gold_count,
        "supported_matched_count": supported_matched_count,
        "missed_count": len(missed),
        "false_positive_count": len(false_positives),
        "recall": _round_metric(matched_count / gold_count) if gold_count else None,
        "precision": _round_metric(matched_count / prediction_count) if prediction_count else None,
        "expression_accuracy_on_matches": _round_metric(expression_correct_count / supported_matched_count)
        if supported_matched_count
        else None,
        "matches": matches,
        "missed": missed,
        "false_positives": false_positives,
    }


def load_annotation_episodes(annotation_dir: Path) -> list[tuple[str, list[dict[str, Any]], Path]]:
    episodes: list[tuple[str, list[dict[str, Any]], Path]] = []
    for path in sorted(annotation_dir.glob("*.annotation.json")):
        video_id, annotations = _valid_gold_annotations(read_json(path))
        if not video_id:
            continue
        episodes.append((video_id, annotations, path))
    return episodes


def resolve_algorithm_output_path(algorithm_output_root: Path, video_id: str) -> Path | None:
    for filename in ALGORITHM_OUTPUT_FILENAMES:
        output_path = algorithm_output_root / video_id / filename
        if output_path.exists():
            return output_path
    return None


def load_algorithm_predictions(algorithm_output_root: Path, video_id: str) -> tuple[list[dict[str, Any]], bool, Path | None]:
    output_path = resolve_algorithm_output_path(algorithm_output_root, video_id)
    if output_path is None:
        return [], True, None
    return _valid_predictions(read_json(output_path)), False, output_path


def summarize_episode_results(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    gold_count = sum(int(episode["gold_count"]) for episode in episodes)
    prediction_count = sum(int(episode["prediction_count"]) for episode in episodes)
    matched_count = sum(int(episode["matched_count"]) for episode in episodes)
    expression_correct_count = sum(int(episode["expression_correct_count"]) for episode in episodes)
    missed_count = sum(int(episode["missed_count"]) for episode in episodes)
    false_positive_count = sum(int(episode["false_positive_count"]) for episode in episodes)
    unsupported_gold_count = sum(int(episode.get("unsupported_gold_count", 0)) for episode in episodes)
    supported_matched_count = sum(int(episode.get("supported_matched_count", 0)) for episode in episodes)
    return {
        "episode_count": len(episodes),
        "gold_count": gold_count,
        "prediction_count": prediction_count,
        "matched_count": matched_count,
        "expression_correct_count": expression_correct_count,
        "unsupported_gold_count": unsupported_gold_count,
        "supported_matched_count": supported_matched_count,
        "missed_count": missed_count,
        "false_positive_count": false_positive_count,
        "recall": _round_metric(matched_count / gold_count) if gold_count else None,
        "precision": _round_metric(matched_count / prediction_count) if prediction_count else None,
        "expression_accuracy_on_matches": _round_metric(expression_correct_count / supported_matched_count)
        if supported_matched_count
        else None,
    }


def build_report(*, annotation_dir: Path, algorithm_output_root: Path, tolerance_sec: float) -> dict[str, Any]:
    episode_results: list[dict[str, Any]] = []
    for video_id, annotations, annotation_path in load_annotation_episodes(annotation_dir):
        predictions, missing_algorithm_output, algorithm_output_path = load_algorithm_predictions(algorithm_output_root, video_id)
        result = evaluate_episode(
            video_id=video_id,
            gold_annotations=annotations,
            predictions=predictions,
            tolerance_sec=tolerance_sec,
            missing_algorithm_output=missing_algorithm_output,
        )
        result["annotation_path"] = str(annotation_path)
        result["algorithm_output_path"] = None if missing_algorithm_output or algorithm_output_path is None else str(algorithm_output_path)
        episode_results.append(result)

    return {
        "created_at": now_iso(),
        "annotation_dir": str(annotation_dir),
        "algorithm_output_root": str(algorithm_output_root),
        "tolerance_sec": tolerance_sec,
        "summary": summarize_episode_results(episode_results),
        "episodes": episode_results,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate expression trigger outputs against gold annotation files.")
    parser.add_argument("--annotation-dir", type=Path, default=DEFAULT_ANNOTATION_DIR)
    parser.add_argument("--algorithm-output-root", type=Path, default=DEFAULT_ALGORITHM_OUTPUT_ROOT)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--tolerance-sec", type=float, default=10.0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        annotation_dir=args.annotation_dir,
        algorithm_output_root=args.algorithm_output_root,
        tolerance_sec=args.tolerance_sec,
    )
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = report["summary"]
    print(
        "Evaluation complete: "
        f"episodes={summary['episode_count']} "
        f"gold={summary['gold_count']} "
        f"predictions={summary['prediction_count']} "
        f"matched={summary['matched_count']} "
        f"recall={summary['recall']} "
        f"precision={summary['precision']} "
        f"report={args.report_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
