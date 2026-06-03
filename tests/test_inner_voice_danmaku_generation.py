from __future__ import annotations

from pathlib import Path
import unittest

from pipelines.inner_voice_danmaku_generation import (
    InnerVoiceDanmakuPipeline,
    build_inner_voice_prompt,
    generate_inner_voice_danmaku,
)


class FakeLlmClient:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []
        self.last_call_diagnostics: dict[str, object] = {"status": "success", "usage": {"total_tokens": 42}}

    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path] | None = None,
        frame_timestamps_seconds: list[float] | None = None,
        max_tokens: int = 4800,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "image_paths": image_paths or [],
                "frame_timestamps_seconds": frame_timestamps_seconds or [],
                "max_tokens": max_tokens,
            }
        )
        return self.response


class InnerVoiceDanmakuGenerationTest(unittest.TestCase):
    def test_builds_actor_charm_cue_from_rule_cluster_without_llm(self) -> None:
        result = generate_inner_voice_danmaku(
            video_id="demo_ep01",
            series_id="demo",
            episode_id="ep01",
            danmaku_items=[
                {"danmaku_id": "dm_1", "time_sec": 10.0, "text": "男主这个眼神绝了", "digg_count": 8},
                {"danmaku_id": "dm_2", "time_sec": 11.0, "text": "他眼神真的好帅", "digg_count": 3},
                {"danmaku_id": "dm_3", "time_sec": 12.0, "text": "好帅好帅", "digg_count": 1},
                {"danmaku_id": "dm_4", "time_sec": 13.0, "text": "哈哈哈哈哈哈", "digg_count": 20},
            ],
            llm_client=None,
            enable_llm_semantic=False,
            window_sec=8.0,
            step_sec=2.0,
            min_window_danmaku_count=2,
            min_unique_text_count=2,
            min_window_score=2.0,
            max_cues_per_episode=4,
            duration_sec=5.0,
        )

        self.assertEqual(result["videoId"], "demo_ep01")
        self.assertEqual(len(result["cues"]), 1)
        cue = result["cues"][0]
        self.assertEqual(cue["cueId"], "iv_demo_ep01_001")
        self.assertEqual(cue["highlightId"], "iv_demo_ep01_001")
        self.assertEqual(cue["triggerTime"], 10.0)
        self.assertEqual(cue["durationSec"], 5.0)
        self.assertEqual(cue["text"], "男主这个眼神绝了")
        self.assertEqual(cue["danmakuTrack"], 0)
        self.assertEqual(result["debug"]["selectedCueCount"], 1)
        self.assertEqual(result["debug"]["cues"][0]["intentType"], "actor_charm")
        self.assertIn("dm_1", result["debug"]["cues"][0]["sourceCommentIds"])

    def test_repeated_high_semantic_text_is_not_rejected_by_unique_text_count(self) -> None:
        result = generate_inner_voice_danmaku(
            video_id="demo_ep01",
            series_id="demo",
            episode_id="ep01",
            danmaku_items=[
                {"danmaku_id": "dm_1", "time_sec": 10.0, "text": "男主这个眼神绝了", "digg_count": 1},
                {"danmaku_id": "dm_2", "time_sec": 11.0, "text": "男主这个眼神绝了", "digg_count": 1},
                {"danmaku_id": "dm_3", "time_sec": 12.0, "text": "男主这个眼神绝了", "digg_count": 1},
                {"danmaku_id": "dm_4", "time_sec": 13.0, "text": "男主这个眼神绝了", "digg_count": 1},
            ],
            llm_client=None,
            enable_llm_semantic=False,
            window_sec=8.0,
            step_sec=2.0,
            min_window_danmaku_count=4,
            min_unique_text_count=3,
            min_window_score=4.0,
            max_cues_per_episode=4,
        )

        self.assertEqual(len(result["cues"]), 1)
        self.assertEqual(result["cues"][0]["text"], "男主这个眼神绝了")
        self.assertEqual(result["debug"]["windows"][0]["uniqueTextCount"], 1)
        self.assertEqual(result["debug"]["windows"][0]["repeatTextCount"], 4)
        self.assertEqual(result["debug"]["cues"][0]["sourceCommentIds"], ["dm_1", "dm_2", "dm_3", "dm_4"])

    def test_uses_llm_for_plot_reaction_and_meme_inside_candidate_windows(self) -> None:
        fake_client = FakeLlmClient(
            {
                "clusters": [
                    {
                        "intentType": "plot_reaction",
                        "representativeText": "她终于怼回去了",
                        "sourceCommentIds": ["dm_1", "dm_2"],
                        "confidence": 0.88,
                        "reason": "多条弹幕都在表达女主反击带来的即时反应。",
                    },
                    {
                        "intentType": "prediction",
                        "representativeText": "我就知道要反转",
                        "sourceCommentIds": ["dm_3"],
                        "confidence": 0.91,
                        "reason": "第一版不支持这个类型。",
                    },
                ]
            }
        )

        result = generate_inner_voice_danmaku(
            video_id="demo_ep01",
            series_id="demo",
            episode_id="ep01",
            danmaku_items=[
                {"danmaku_id": "dm_1", "time_sec": 20.0, "text": "女主终于怼回去了啊", "digg_count": 6},
                {"danmaku_id": "dm_2", "time_sec": 21.0, "text": "她终于怼他了", "digg_count": 2},
                {"danmaku_id": "dm_3", "time_sec": 22.0, "text": "我就知道要反转", "digg_count": 9},
                {"danmaku_id": "dm_4", "time_sec": 23.0, "text": "这段太爽了", "digg_count": 1},
            ],
            llm_client=fake_client,
            enable_llm_semantic=True,
            window_sec=8.0,
            step_sec=2.0,
            min_window_danmaku_count=2,
            min_unique_text_count=2,
            min_window_score=2.0,
            max_cues_per_episode=4,
        )

        self.assertEqual(len(fake_client.calls), 1)
        self.assertIn("Only identify plot_reaction and meme", str(fake_client.calls[0]["user_prompt"]))
        self.assertIn("dm_1", str(fake_client.calls[0]["user_prompt"]))
        self.assertEqual(len(result["cues"]), 1)
        self.assertEqual(result["cues"][0]["text"], "她终于怼回去了")
        self.assertEqual(result["debug"]["cues"][0]["intentType"], "plot_reaction")
        self.assertEqual(result["debug"]["cues"][0]["sourceCommentIds"], ["dm_1", "dm_2"])
        self.assertEqual(result["debug"]["llmCallCount"], 1)

    def test_rejects_llm_cluster_without_valid_source_ids(self) -> None:
        fake_client = FakeLlmClient(
            {
                "clusters": [
                    {
                        "intentType": "meme",
                        "representativeText": "这谁顶得住",
                        "sourceCommentIds": ["unknown_dm"],
                        "confidence": 0.9,
                        "reason": "source id 不在输入里。",
                    }
                ]
            }
        )

        result = generate_inner_voice_danmaku(
            video_id="demo_ep01",
            series_id="demo",
            episode_id="ep01",
            danmaku_items=[
                {"danmaku_id": "dm_1", "time_sec": 30.0, "text": "这谁顶得住", "digg_count": 5},
                {"danmaku_id": "dm_2", "time_sec": 31.0, "text": "禁止这么会演", "digg_count": 3},
            ],
            llm_client=fake_client,
            enable_llm_semantic=True,
            window_sec=8.0,
            step_sec=2.0,
            min_window_danmaku_count=2,
            min_unique_text_count=2,
            min_window_score=2.0,
        )

        self.assertEqual(result["cues"], [])
        self.assertEqual(result["debug"]["filteredCandidateCount"], 1)

    def test_build_inner_voice_prompt_contains_top_comments_and_subtitle_context(self) -> None:
        prompt = build_inner_voice_prompt(
            video_id="demo_ep01",
            window={
                "windowId": "ivw_demo_ep01_001",
                "startTime": 10.0,
                "endTime": 18.0,
                "topComments": [
                    {"commentId": "dm_1", "timeSec": 11.0, "text": "她终于怼回去了", "diggCount": 6},
                ],
            },
            subtitle_context="女主：我不会再忍了",
        )

        self.assertIn("Only identify plot_reaction and meme", prompt)
        self.assertIn("dm_1", prompt)
        self.assertIn("她终于怼回去了", prompt)
        self.assertIn("女主：我不会再忍了", prompt)

    def test_pipeline_records_progress_events(self) -> None:
        events: list[tuple[str, dict[str, object]]] = []
        pipeline = InnerVoiceDanmakuPipeline(
            llm_client=None,
            enable_llm_semantic=False,
            progress_callback=lambda event, payload: events.append((event, payload)),
            min_window_danmaku_count=2,
            min_unique_text_count=2,
            min_window_score=2.0,
        )

        pipeline.run(
            video_id="demo_ep01",
            series_id="demo",
            episode_id="ep01",
            danmaku_items=[
                {"danmaku_id": "dm_1", "time_sec": 10.0, "text": "男主这个眼神绝了", "digg_count": 8},
                {"danmaku_id": "dm_2", "time_sec": 11.0, "text": "他眼神真的好帅", "digg_count": 3},
            ],
        )

        event_names = [event for event, _payload in events]
        self.assertEqual(event_names[0], "prepared")
        self.assertIn("windows_built", event_names)
        self.assertIn("window_processing_start", event_names)
        self.assertIn("actor_candidate_built", event_names)
        self.assertIn("candidates_built", event_names)
        self.assertEqual(event_names[-1], "completed")
        self.assertEqual(events[0][1]["source_danmaku_count"], 2)
        self.assertEqual(events[-1][1]["selected_cue_count"], 1)

    def test_pipeline_reports_window_level_llm_progress(self) -> None:
        fake_client = FakeLlmClient(
            {
                "clusters": [
                    {
                        "intentType": "plot_reaction",
                        "representativeText": "她终于怼回去了",
                        "sourceCommentIds": ["dm_1", "dm_2"],
                        "confidence": 0.88,
                        "reason": "多条弹幕都在表达女主反击。",
                    }
                ]
            }
        )
        events: list[tuple[str, dict[str, object]]] = []
        pipeline = InnerVoiceDanmakuPipeline(
            llm_client=fake_client,
            enable_llm_semantic=True,
            progress_callback=lambda event, payload: events.append((event, payload)),
            min_window_danmaku_count=2,
            min_unique_text_count=2,
            min_window_score=2.0,
        )

        pipeline.run(
            video_id="demo_ep01",
            series_id="demo",
            episode_id="ep01",
            danmaku_items=[
                {"danmaku_id": "dm_1", "time_sec": 20.0, "text": "女主终于怼回去了啊", "digg_count": 6},
                {"danmaku_id": "dm_2", "time_sec": 21.0, "text": "她终于怼他了", "digg_count": 2},
            ],
        )

        event_names = [event for event, _payload in events]
        self.assertIn("window_processing_start", event_names)
        self.assertIn("llm_window_start", event_names)
        self.assertIn("llm_window_done", event_names)
        self.assertEqual(events[event_names.index("window_processing_start")][1]["window_index"], 1)
        self.assertEqual(events[event_names.index("window_processing_start")][1]["window_count"], 1)
        self.assertEqual(events[event_names.index("llm_window_start")][1]["top_comment_count"], 2)
        self.assertEqual(events[event_names.index("llm_window_done")][1]["llm_candidate_count"], 1)
        self.assertEqual(events[event_names.index("llm_window_done")][1]["filtered_candidate_count"], 0)
