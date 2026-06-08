from __future__ import annotations

import json
from pathlib import Path


class FakeLlmClient:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []
        self.last_call_diagnostics: dict[str, object] = {"status": "success", "usage": {"total_tokens": 123}}

    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path] | None = None,
        frame_timestamps_seconds: list[float] | None = None,
        max_tokens: int = 2400,
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


def write_transcription(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "provider": "aliyun",
                "raw_response": {
                    "chunks": [
                        {
                            "offset_seconds": 0.0,
                            "raw_result": {
                                "transcripts": [
                                    {
                                        "sentences": [
                                            {"begin_time": 1000, "end_time": 2500, "text": "你怎么会在这里？"},
                                            {"begin_time": 3000, "end_time": 5200, "text": "有钱没钱都得回家过年。"},
                                        ]
                                    }
                                ]
                            },
                        }
                    ]
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def semantic_clusters_payload() -> dict[str, object]:
    clusters: list[dict[str, object]] = []
    for index in range(1, 55):
        clusters.append(
            {
                "clusterId": f"dsc_demo_ep01_{index:03d}",
                "videoId": "demo_ep01",
                "scoreRank": index,
                "clusterScore": 100.0 - index,
                "commentCount": 10 + index,
                "uniqueTextCount": 3,
                "diggSum": index,
                "peakIntervals": [{"startTime": float(index), "endTime": float(index + 8), "commentCount": 5}],
                "representativeComments": [
                    {
                        "text": f"代表弹幕 {index}-{comment_index}",
                        "sourceCommentIds": [f"dm_{index}_{comment_index}"],
                    }
                    for comment_index in range(1, 5)
                ],
                "examples": [{"text": f"例子弹幕 {index}-{example_index}"} for example_index in range(1, 7)],
            }
        )
    return {
        "sourceCsv": "data/demo.csv",
        "parameters": {"seriesId": "demo", "episodeId": "ep01"},
        "allClustersByScore": clusters,
    }


def test_build_inner_voice_selection_prompt_uses_full_transcription_and_top_clusters(tmp_path: Path) -> None:
    from pipelines.danmaku_inner_voice_selection import build_inner_voice_selection_prompt
    from pipelines.story_chapter.baseline_text import load_utterances_from_transcription

    transcription_path = tmp_path / "video.transcription.json"
    write_transcription(transcription_path)

    prompt = build_inner_voice_selection_prompt(
        video_id="demo_ep01",
        utterances=load_utterances_from_transcription(transcription_path),
        clusters=semantic_clusters_payload()["allClustersByScore"],  # type: ignore[arg-type]
        top_cluster_count=50,
        representative_comment_count=3,
        example_count=5,
    )

    assert "整集字幕" in prompt
    assert "你怎么会在这里？" in prompt
    assert "有钱没钱都得回家过年。" in prompt
    assert "dsc_demo_ep01_001" in prompt
    assert "dsc_demo_ep01_050" in prompt
    assert "dsc_demo_ep01_051" not in prompt
    assert "代表弹幕 1-3" in prompt
    assert "代表弹幕 1-4" not in prompt
    assert "例子弹幕 1-5" in prompt
    assert "例子弹幕 1-6" not in prompt
    assert "不要输出 triggerTime" in prompt


def test_select_inner_voice_candidates_from_semantic_clusters_filters_invalid_outputs(tmp_path: Path) -> None:
    from pipelines.danmaku_inner_voice_selection import select_inner_voice_candidates_from_semantic_clusters

    transcription_path = tmp_path / "video.transcription.json"
    write_transcription(transcription_path)
    fake_client = FakeLlmClient(
        {
            "selected": [
                {
                    "clusterId": "dsc_demo_ep01_002",
                    "text": "有钱没钱都得回家过年",
                    "suitabilityScore": 0.91,
                    "reason": "表达完整，且和剧情台词形成共鸣。",
                    "sourceCommentIds": ["dm_2_1"],
                },
                {
                    "clusterId": "unknown",
                    "text": "未知簇",
                    "suitabilityScore": 0.95,
                    "reason": "应被过滤。",
                },
                {
                    "clusterId": "dsc_demo_ep01_003",
                    "text": "哈哈哈",
                    "suitabilityScore": 0.99,
                    "reason": "简单情绪，应被过滤。",
                },
            ],
            "rejectedSummary": [{"clusterId": "dsc_demo_ep01_001", "reason": "纯名词复读"}],
        }
    )
    events: list[tuple[str, dict[str, object]]] = []

    result = select_inner_voice_candidates_from_semantic_clusters(
        semantic_clusters_payload(),
        transcription_path=transcription_path,
        llm_client=fake_client,
        top_cluster_count=50,
        max_tokens=1600,
        progress_callback=lambda event, payload: events.append((event, payload)),
    )

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["max_tokens"] == 1600
    assert result["candidateCount"] == 1
    assert result["candidates"][0]["candidateId"] == "ivcluster_demo_ep01_001"
    assert result["candidates"][0]["clusterId"] == "dsc_demo_ep01_002"
    assert result["candidates"][0]["text"] == "有钱没钱都得回家过年"
    assert result["candidates"][0]["sourceCommentIds"] == ["dm_2_1"]
    assert result["debug"]["filteredSelections"][0]["reason"] == "unknown_cluster_id"
    assert result["debug"]["filteredSelections"][1]["reason"] == "simple_emotion_text"
    assert result["debug"]["llmCalls"][0]["usage"]["total_tokens"] == 123
    assert [event for event, _payload in events] == ["prepared", "llm_start", "llm_done", "completed"]


def test_inner_voice_selection_script_resolves_transcription_from_assets_root(tmp_path: Path) -> None:
    from scripts.run_danmaku_inner_voice_selection import main

    semantic_path = tmp_path / "semantic_clusters.json"
    output_path = tmp_path / "inner_voice_selection.json"
    assets_root = tmp_path / "assets"
    transcription_path = assets_root / "demo" / "ep01" / "video.transcription.json"
    transcription_path.parent.mkdir(parents=True)
    write_transcription(transcription_path)
    semantic_path.write_text(json.dumps(semantic_clusters_payload(), ensure_ascii=False), encoding="utf-8")
    fake_client = FakeLlmClient(
        {
            "selected": [
                {
                    "clusterId": "dsc_demo_ep01_002",
                    "text": "有钱没钱都得回家过年",
                    "suitabilityScore": 0.9,
                    "reason": "表达完整。",
                }
            ]
        }
    )

    result = main(
        [
            "--semantic-clusters-path",
            str(semantic_path),
            "--output-path",
            str(output_path),
            "--assets-root",
            str(assets_root),
            "--series-id",
            "demo",
            "--episode-id",
            "ep01",
        ],
        llm_client=fake_client,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["sourceTranscription"] == str(transcription_path)
    assert payload["candidateCount"] == 1
