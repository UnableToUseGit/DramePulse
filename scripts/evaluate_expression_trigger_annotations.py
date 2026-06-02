from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


DEFAULT_ANNOTATION_DIR = Path("data/annotations/expression_trigger_gold")
DEFAULT_ALGORITHM_OUTPUT_ROOT = Path("output/expression_trigger")
DEFAULT_REPORT_PATH = Path("output/expression_trigger_annotation_eval/report.json")


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
        try:
            cue_time = float(item["cue_time"])
        except (KeyError, TypeError, ValueError):
            continue
        primary_expression = str(item.get("primary_expression") or "").strip()
        if cue_time < 0 or not primary_expression:
            continue
        normalized.append(
            {
                "annotation_id": str(item.get("annotation_id") or f"gold_{video_id}_{index:03d}"),
                "cue_time": _round_time(cue_time),
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
        try:
            cue_time = float(item["cue_time"])
        except (KeyError, TypeError, ValueError):
            continue
        primary_expression = str(item.get("primary_expression") or item.get("emotion") or "").strip()
        if cue_time < 0 or not primary_expression:
            continue
        predictions.append(
            {
                "trigger_id": str(item.get("trigger_id") or f"pred_{index:03d}"),
                "cue_time": _round_time(cue_time),
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
        for prediction_index in unmatched_prediction_indexes:
            prediction = predictions[prediction_index]
            delta = abs(float(prediction["cue_time"]) - float(annotation["cue_time"]))
            if delta > tolerance_sec:
                continue
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_index = prediction_index
        if best_index is None or best_delta is None:
            missed.append(annotation)
            continue

        unmatched_prediction_indexes.remove(best_index)
        prediction = predictions[best_index]
        expression_match = prediction["primary_expression"] == annotation["primary_expression"]
        matches.append(
            {
                "annotation": annotation,
                "prediction": prediction,
                "time_delta_sec": _round_time(best_delta),
                "expression_match": expression_match,
            }
        )

    false_positives = [predictions[index] for index in sorted(unmatched_prediction_indexes)]
    matched_count = len(matches)
    gold_count = len(gold_annotations)
    prediction_count = len(predictions)
    expression_correct_count = sum(1 for match in matches if match["expression_match"])

    return {
        "video_id": video_id,
        "missing_algorithm_output": missing_algorithm_output,
        "gold_count": gold_count,
        "prediction_count": prediction_count,
        "matched_count": matched_count,
        "expression_correct_count": expression_correct_count,
        "missed_count": len(missed),
        "false_positive_count": len(false_positives),
        "recall": _round_metric(matched_count / gold_count) if gold_count else None,
        "precision": _round_metric(matched_count / prediction_count) if prediction_count else None,
        "expression_accuracy_on_matches": _round_metric(expression_correct_count / matched_count) if matched_count else None,
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


def load_algorithm_predictions(algorithm_output_root: Path, video_id: str) -> tuple[list[dict[str, Any]], bool]:
    output_path = algorithm_output_root / video_id / "highlight_recognition.json"
    if not output_path.exists():
        return [], True
    return _valid_predictions(read_json(output_path)), False


def summarize_episode_results(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    gold_count = sum(int(episode["gold_count"]) for episode in episodes)
    prediction_count = sum(int(episode["prediction_count"]) for episode in episodes)
    matched_count = sum(int(episode["matched_count"]) for episode in episodes)
    expression_correct_count = sum(int(episode["expression_correct_count"]) for episode in episodes)
    missed_count = sum(int(episode["missed_count"]) for episode in episodes)
    false_positive_count = sum(int(episode["false_positive_count"]) for episode in episodes)
    return {
        "episode_count": len(episodes),
        "gold_count": gold_count,
        "prediction_count": prediction_count,
        "matched_count": matched_count,
        "expression_correct_count": expression_correct_count,
        "missed_count": missed_count,
        "false_positive_count": false_positive_count,
        "recall": _round_metric(matched_count / gold_count) if gold_count else None,
        "precision": _round_metric(matched_count / prediction_count) if prediction_count else None,
        "expression_accuracy_on_matches": _round_metric(expression_correct_count / matched_count) if matched_count else None,
    }


def build_report(*, annotation_dir: Path, algorithm_output_root: Path, tolerance_sec: float) -> dict[str, Any]:
    episode_results: list[dict[str, Any]] = []
    for video_id, annotations, annotation_path in load_annotation_episodes(annotation_dir):
        predictions, missing_algorithm_output = load_algorithm_predictions(algorithm_output_root, video_id)
        result = evaluate_episode(
            video_id=video_id,
            gold_annotations=annotations,
            predictions=predictions,
            tolerance_sec=tolerance_sec,
            missing_algorithm_output=missing_algorithm_output,
        )
        result["annotation_path"] = str(annotation_path)
        result["algorithm_output_path"] = (
            None if missing_algorithm_output else str(algorithm_output_root / video_id / "highlight_recognition.json")
        )
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
