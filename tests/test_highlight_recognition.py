from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from pipelines.highlight_recognition import (
    HighlightRecognitionPipeline,
    parse_highlight_assets,
)
from pipelines.utils import SubtitleSegment, build_sample_timestamps, format_subtitle_timeline


class BuildSampleTimestampsTest(unittest.TestCase):
    def test_build_sample_timestamps_uses_sample_interval_as_frame_gap(self) -> None:
        timestamps = build_sample_timestamps(
            duration_sec=3.0,
            sample_interval_sec=1.0,
        )

        self.assertEqual(timestamps, [0.0, 1.0, 2.0])

    def test_build_sample_timestamps_resamples_evenly_when_over_max_frames(self) -> None:
        timestamps = build_sample_timestamps(
            duration_sec=10.0,
            sample_interval_sec=1.0,
            max_frames=3,
        )

        self.assertEqual(timestamps, [0.0, 5.0, 9.999])


class SubtitleTimelineTest(unittest.TestCase):
    def test_format_subtitle_timeline_uses_timestamped_lines(self) -> None:
        text = format_subtitle_timeline(
            [
                SubtitleSegment(start=38.0, end=41.2, text="你根本不知道他是谁。"),
                SubtitleSegment(start=41.3, end=45.0, text="他就是顾氏集团真正的继承人。"),
            ]
        )

        self.assertEqual(
            text,
            "\n".join(
                [
                    "[SUBTITLE_TIMELINE]",
                    "[00:38.000 - 00:41.200] 你根本不知道他是谁。",
                    "[00:41.300 - 00:45.000] 他就是顾氏集团真正的继承人。",
                    "[/SUBTITLE_TIMELINE]",
                ]
            ),
        )


class ParseHighlightAssetsTest(unittest.TestCase):
    def test_parse_highlight_assets_fills_required_fields(self) -> None:
        raw = {
            "highlights": [
                {
                    "start_time": 38.0,
                    "end_time": 46.0,
                    "highlight_type": "身份揭露",
                    "emotion": "震惊",
                    "intensity": 0.92,
                    "summary": "男主真实身份曝光，反派震惊。",
                    "reason": "前文一直铺垫男主被轻视，此处身份反转带来强爽点。",
                    "confidence": 0.88,
                }
            ]
        }

        assets = parse_highlight_assets(
            raw,
            video_id="v_001",
            highlight_score=0.81,
        )

        self.assertEqual(len(assets), 1)
        asset = assets[0]
        self.assertEqual(asset["video_id"], "v_001")
        self.assertEqual(asset["highlight_id"], "h_v_001_001")
        self.assertEqual(asset["status"], "verified")
        self.assertEqual(asset["highlight_score"], 0.81)


class PipelineSmokeTest(unittest.TestCase):
    def test_pipeline_returns_assets(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def generate_json_multimodal(
                self,
                *,
                system_prompt: str,
                user_prompt: str,
                image_paths: list[Path],
                frame_timestamps_seconds: list[float] | None = None,
                max_tokens: int = 1800,
            ) -> dict[str, object]:
                self.calls.append(
                    {
                        "system_prompt": system_prompt,
                        "user_prompt": user_prompt,
                        "image_paths": image_paths,
                        "frame_timestamps_seconds": frame_timestamps_seconds,
                        "max_tokens": max_tokens,
                    }
                )
                return {
                    "highlights": [
                        {
                            "start_time": 0.0,
                            "end_time": 1.0,
                            "highlight_type": "冲突爆发",
                            "emotion": "愤怒",
                            "intensity": 0.7,
                            "summary": "冲突升级。",
                            "reason": "测试用高光。",
                            "confidence": 0.9,
                        }
                    ]
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            subtitle_path = tmp_path / "subtitle.srt"
            video_path.write_bytes(b"fake-video")
            subtitle_path.write_text(
                "\n".join(
                    [
                        "1",
                        "00:00:00,000 --> 00:00:01,000",
                        "第一句",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            pipeline = HighlightRecognitionPipeline(
                llm_client=FakeClient(),
                sample_interval_sec=1.0,
            )
            result = pipeline.run(
                video_id="v_001",
                video_file_path=video_path,
                subtitle_file_path=subtitle_path,
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["video_id"], "v_001")
        self.assertEqual(result[0]["highlight_type"], "冲突爆发")
        self.assertIn("Do not invent plot details", str(pipeline.llm_client.calls[0]["user_prompt"]))


if __name__ == "__main__":
    unittest.main()
