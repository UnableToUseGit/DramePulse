from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.evaluate_story_chapter_workflow import evaluate_episode, main


class StoryChapterWorkflowEvaluationScriptTest(unittest.TestCase):
    def test_evaluate_episode_matches_internal_boundaries_with_tolerance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gold_path = root / "gold" / "demo_ep01.annotation.json"
            pred_path = root / "pred" / "demo_ep01" / "story_chapters.json"
            gold_path.parent.mkdir(parents=True)
            pred_path.parent.mkdir(parents=True)
            gold_path.write_text(
                json.dumps(
                    {
                        "video_id": "demo_ep01",
                        "duration_seconds": 30.0,
                        "boundaries": [
                            {"time": 10.0, "ending_chapter_summary": "A"},
                            {"time": 20.0, "ending_chapter_summary": "B"},
                        ],
                        "final_chapter_summary": "C",
                        "chapters": [
                            {"start_time": 0.0, "end_time": 10.0, "summary": "A"},
                            {"start_time": 10.0, "end_time": 20.0, "summary": "B"},
                            {"start_time": 20.0, "end_time": 30.0, "summary": "C"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            pred_path.write_text(
                json.dumps(
                    {
                        "video_id": "demo_ep01",
                        "story_chapters": [
                            {"start_time": 0.0, "end_time": 9.0, "title": "A"},
                            {"start_time": 9.0, "end_time": 21.0, "title": "B"},
                            {"start_time": 21.0, "end_time": 25.0, "title": "extra"},
                            {"start_time": 25.0, "end_time": 30.0, "title": "C"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = evaluate_episode(gold_path=gold_path, prediction_path=pred_path, tolerance_seconds=2.0)

        self.assertEqual(result["video_id"], "demo_ep01")
        self.assertEqual(result["gold_boundary_count"], 2)
        self.assertEqual(result["predicted_boundary_count"], 3)
        self.assertEqual(result["matched_boundary_count"], 2)
        self.assertEqual(result["false_positive_count"], 1)
        self.assertEqual(result["false_negative_count"], 0)
        self.assertAlmostEqual(result["boundary_precision"], 2 / 3)
        self.assertAlmostEqual(result["boundary_recall"], 1.0)
        self.assertEqual(result["mean_abs_boundary_error_seconds"], 1.0)
        self.assertEqual(result["matched_boundaries"][0]["gold_time"], 10.0)
        self.assertEqual(result["matched_boundaries"][0]["predicted_time"], 9.0)
        self.assertEqual(result["unmatched_predicted_boundaries"], [25.0])

    def test_main_writes_summary_for_gold_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gold_root = root / "gold"
            prediction_root = root / "pred"
            report_path = root / "report.json"
            gold_root.mkdir()
            (prediction_root / "demo_ep01").mkdir(parents=True)
            (gold_root / "demo_ep01.annotation.json").write_text(
                json.dumps(
                    {
                        "video_id": "demo_ep01",
                        "duration_seconds": 12.0,
                        "boundaries": [{"time": 6.0, "ending_chapter_summary": "A"}],
                        "final_chapter_summary": "B",
                        "chapters": [
                            {"start_time": 0.0, "end_time": 6.0, "summary": "A"},
                            {"start_time": 6.0, "end_time": 12.0, "summary": "B"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (prediction_root / "demo_ep01" / "story_chapters.json").write_text(
                json.dumps(
                    {
                        "video_id": "demo_ep01",
                        "story_chapters": [
                            {"start_time": 0.0, "end_time": 6.5},
                            {"start_time": 6.5, "end_time": 12.0},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = main(
                [
                    "--gold-root",
                    str(gold_root),
                    "--prediction-root",
                    str(prediction_root),
                    "--report-path",
                    str(report_path),
                    "--tolerance-seconds",
                    "1.0",
                ]
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        self.assertEqual(report["total_episodes"], 1)
        self.assertEqual(report["episodes"][0]["video_id"], "demo_ep01")
        self.assertEqual(report["macro_boundary_recall"], 1.0)


if __name__ == "__main__":
    unittest.main()
