from __future__ import annotations

import json
from pathlib import Path


class FakeEmbeddingClient:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "帅" in text or "眼神" in text else [0.0, 1.0] for text in texts]


class FakeLlmClient:
    last_call_diagnostics: dict[str, object] = {"usage": {"total_tokens": 99}}

    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path] | None = None,
        frame_timestamps_seconds: list[float] | None = None,
        max_tokens: int = 2400,
    ) -> dict[str, object]:
        cluster_id = "dsc_beiwang_ep02_001" if "beiwang_ep02" in user_prompt else "dsc_beiwang_ep01_001"
        return {
            "selected": [
                {
                    "clusterId": cluster_id,
                    "text": "这个眼神太帅了",
                    "suitabilityScore": 0.92,
                    "reason": "演员魅力表达明确。",
                }
            ]
        }


def write_batch_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "剧名称,group_title,发弹幕时刻相对于视频起始时间偏移量,累计点赞数,弹幕内容",
                "北往,第1集,10000,3,这个眼神太帅了",
                "北往,第1集,10800,1,男主眼神绝了",
                "北往,第1集,11600,2,老公好帅",
                "北往,第2集,20000,4,第二集眼神太帅了",
                "北往,第2集,20800,1,男主第二集眼神绝了",
                "北往,第2集,21600,2,第二集老公好帅",
            ]
        )
        + "\n",
        encoding="gb18030",
    )


def write_transcription(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True)
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
                                            {"begin_time": 1000, "end_time": 2500, "text": text},
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


def test_inner_voice_danmaku_batch_runs_selected_episodes(tmp_path: Path) -> None:
    from scripts.inner_voice_danmaku.run_batch import main

    csv_path = tmp_path / "圈选剧前5集弹幕.csv"
    assets_root = tmp_path / "assets"
    output_dir = tmp_path / "output"
    write_batch_csv(csv_path)
    write_transcription(assets_root / "beiwang" / "ep01" / "video.transcription.json", "第一集台词")
    write_transcription(assets_root / "beiwang" / "ep02" / "video.transcription.json", "第二集台词")

    result = main(
        [
            "--csv-path",
            str(csv_path),
            "--assets-root",
            str(assets_root),
            "--output-dir",
            str(output_dir),
            "--series-id",
            "beiwang",
            "--episode-ids",
            "ep01",
            "ep02",
            "--cluster-method",
            "connected_components",
            "--min-cluster-comment-count",
            "2",
        ],
        embedding_client=FakeEmbeddingClient(),
        llm_client=FakeLlmClient(),
    )

    assert result == 0
    for episode_id in ["ep01", "ep02"]:
        semantic_path = output_dir / f"semantic_clusters_beiwang_{episode_id}.json"
        selection_path = output_dir / f"inner_voice_selection_beiwang_{episode_id}.json"
        plan_path = output_dir / f"interaction_plan_beiwang_{episode_id}.json"
        assert semantic_path.exists()
        assert selection_path.exists()
        assert plan_path.exists()
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assert plan[0]["series_id"] == "beiwang"
        assert plan[0]["interaction_mode"] == "inner_voice_danmaku"
