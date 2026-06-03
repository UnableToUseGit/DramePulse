from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def make_episode(data_root: Path, *, series_id: str, episode_id: str) -> None:
    episode_dir = data_root / series_id / episode_id
    episode_dir.mkdir(parents=True)
    (episode_dir / "video.mp4").write_bytes(b"video")
    (episode_dir / "video.srt").write_text("1\n00:00:05,000 --> 00:00:08,000\n测试字幕\n", encoding="utf-8")
    (episode_dir / "douyin.json").write_text(
        json.dumps(
            {
                "danmaku": [
                    {"danmaku_id": "json_dm_1", "time_sec": 10.0, "text": "json 弹幕", "digg_count": 1}
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_inner_voice_batch_writes_cues_and_debug(tmp_path: Path) -> None:
    from scripts.run_inner_voice_danmaku_generation import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")

    class FakePipeline:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def run(
            self,
            *,
            video_id: str,
            series_id: str,
            episode_id: str,
            danmaku_items: list[dict[str, object]],
        ) -> dict[str, object]:
            self.calls.append(
                {
                    "video_id": video_id,
                    "series_id": series_id,
                    "episode_id": episode_id,
                    "danmaku_items": danmaku_items,
                }
            )
            return {
                "videoId": video_id,
                "seriesId": series_id,
                "episodeId": episode_id,
                "createdAt": "2026-06-03T00:00:00Z",
                "cues": [
                    {
                        "cueId": f"iv_{video_id}_001",
                        "videoId": video_id,
                        "highlightId": f"iv_{video_id}_001",
                        "triggerTime": 10.0,
                        "durationSec": 5.0,
                        "text": "男主这个眼神绝了",
                        "danmakuTrack": 0,
                    }
                ],
                "debug": {
                    "sourceDanmakuCount": len(danmaku_items),
                    "selectedCueCount": 1,
                },
            }

    fake_pipeline = FakePipeline()

    result = main(
        [
            "--data-root",
            str(data_root),
            "--output-root",
            str(output_root),
        ],
        pipeline=fake_pipeline,
    )

    output_dir = output_root / "series_a_ep01"
    cues_payload = json.loads((output_dir / "inner_voice_cues.json").read_text(encoding="utf-8"))
    debug_payload = json.loads((output_dir / "inner_voice_debug.json").read_text(encoding="utf-8"))
    assert result == 0
    assert cues_payload["videoId"] == "series_a_ep01"
    assert cues_payload["cues"][0]["text"] == "男主这个眼神绝了"
    assert cues_payload["debug"]["selectedCueCount"] == 1
    assert debug_payload["selectedCueCount"] == 1
    assert fake_pipeline.calls[0]["video_id"] == "series_a_ep01"
    assert fake_pipeline.calls[0]["danmaku_items"][0]["danmaku_id"] == "json_dm_1"


def test_inner_voice_batch_skips_existing_output_unless_force(tmp_path: Path) -> None:
    from scripts.run_inner_voice_danmaku_generation import main

    data_root = tmp_path / "DataForAlgorithm"
    output_root = tmp_path / "output"
    make_episode(data_root, series_id="series_a", episode_id="ep01")
    output_dir = output_root / "series_a_ep01"
    output_dir.mkdir(parents=True)
    (output_dir / "inner_voice_cues.json").write_text('{"existing": true}\n', encoding="utf-8")

    class FakePipeline:
        def __init__(self) -> None:
            self.call_count = 0

        def run(self, **kwargs: object) -> dict[str, object]:
            self.call_count += 1
            return {
                "videoId": "series_a_ep01",
                "seriesId": "series_a",
                "episodeId": "ep01",
                "createdAt": "2026-06-03T00:00:00Z",
                "cues": [],
                "debug": {},
            }

    fake_pipeline = FakePipeline()
    result = main(
        [
            "--data-root",
            str(data_root),
            "--output-root",
            str(output_root),
        ],
        pipeline=fake_pipeline,
    )
    assert result == 0
    assert fake_pipeline.call_count == 0

    result = main(
        [
            "--data-root",
            str(data_root),
            "--output-root",
            str(output_root),
            "--force",
        ],
        pipeline=fake_pipeline,
    )
    assert result == 0
    assert fake_pipeline.call_count == 1


def test_build_pipeline_passes_inner_voice_options(monkeypatch) -> None:
    import scripts.run_inner_voice_danmaku_generation as batch

    captured: dict[str, object] = {}

    class FakePipeline:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(batch, "build_llm_client", lambda *, env_path: "fake-client")
    monkeypatch.setattr(
        "pipelines.inner_voice_danmaku_generation.InnerVoiceDanmakuPipeline",
        FakePipeline,
    )

    pipeline = batch.build_pipeline(
        env_path=Path(".env.test"),
        enable_llm_semantic=True,
        window_sec=9.0,
        step_sec=3.0,
        min_window_danmaku_count=5,
        min_unique_text_count=3,
        min_window_score=7.0,
        max_cues_per_episode=6,
        duration_sec=4.0,
        min_cue_gap_sec=10.0,
        llm_max_tokens=999,
    )

    assert isinstance(pipeline, FakePipeline)
    assert captured["llm_client"] == "fake-client"
    assert captured["enable_llm_semantic"] is True
    assert captured["window_sec"] == 9.0
    assert captured["step_sec"] == 3.0
    assert captured["min_window_danmaku_count"] == 5
    assert captured["min_unique_text_count"] == 3
    assert captured["min_window_score"] == 7.0
    assert captured["max_cues_per_episode"] == 6
    assert captured["duration_sec"] == 4.0
    assert captured["min_cue_gap_sec"] == 10.0
    assert captured["llm_max_tokens"] == 999
    assert callable(captured["progress_callback"])


def test_print_inner_voice_progress_formats_window_events(capsys) -> None:
    from scripts.run_inner_voice_danmaku_generation import print_inner_voice_progress

    print_inner_voice_progress(
        "window_processing_start",
        {
            "video_id": "beiwang_ep01",
            "window_index": 3,
            "window_count": 34,
            "start_time": 42.0,
            "end_time": 50.0,
            "danmaku_count": 18,
            "score": 21.5,
        },
    )
    print_inner_voice_progress(
        "actor_candidate_built",
        {
            "video_id": "beiwang_ep01",
            "window_index": 3,
            "window_count": 34,
            "text": "男主这个眼神绝了",
            "source_comment_count": 4,
            "candidate_count": 1,
        },
    )
    print_inner_voice_progress(
        "llm_window_start",
        {
            "video_id": "beiwang_ep01",
            "window_index": 3,
            "window_count": 34,
            "top_comment_count": 40,
            "max_tokens": 1200,
        },
    )
    print_inner_voice_progress(
        "llm_window_done",
        {
            "video_id": "beiwang_ep01",
            "window_index": 3,
            "window_count": 34,
            "llm_candidate_count": 1,
            "filtered_candidate_count": 2,
            "candidate_count": 3,
            "elapsed_sec": 7.25,
        },
    )
    print_inner_voice_progress(
        "llm_window_failed",
        {
            "video_id": "beiwang_ep01",
            "window_index": 4,
            "window_count": 34,
            "elapsed_sec": 12.0,
            "error_type": "TimeoutError",
            "error": "request timed out",
        },
    )

    captured = capsys.readouterr()
    assert "[beiwang_ep01] window_processing_start: 3/34 42.0s-50.0s danmaku=18 score=21.5" in captured.out
    assert "[beiwang_ep01] actor_candidate_built: 3/34 text=男主这个眼神绝了 sources=4 candidates=1" in captured.out
    assert "[beiwang_ep01] llm_window_start: 3/34 top_comments=40 max_tokens=1200" in captured.out
    assert "[beiwang_ep01] llm_window_done: 3/34 llm_candidates=1 filtered=2 candidates=3 elapsed=7.25s" in captured.out
    assert "[beiwang_ep01] llm_window_failed: 4/34 elapsed=12.0s error=TimeoutError: request timed out" in captured.out
