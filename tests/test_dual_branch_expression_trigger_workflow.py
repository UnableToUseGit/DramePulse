from __future__ import annotations

from pathlib import Path
from typing import Any

from pipelines.common.media import FrameExtractionResult
from pipelines.expression_trigger.dual_branch_workflow import DualBranchExpressionTriggerPipeline


class FakeLlmClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.last_call_diagnostics: dict[str, Any] = {}

    def generate_json_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path] | None = None,
        frame_timestamps_seconds: list[float] | None = None,
        max_tokens: int = 4800,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "image_paths": image_paths or [],
                "frame_timestamps_seconds": frame_timestamps_seconds or [],
                "max_tokens": max_tokens,
            }
        )
        self.last_call_diagnostics = {
            "status": "success",
            "request_index": len(self.calls),
            "total_tokens": 123,
        }
        return self.responses.pop(0)


def write_srt(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "1",
                "00:00:10,000 --> 00:00:12,000",
                "你凭啥子欺负我娃儿",
                "",
                "2",
                "00:00:18,000 --> 00:00:20,000",
                "我今天就把桌子掀了",
                "",
                "3",
                "00:01:00,000 --> 00:01:02,000",
                "来嘛，我帮你消毒",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_dual_branch_workflow_runs_three_llm_stages(tmp_path: Path, monkeypatch: Any) -> None:
    from pipelines.expression_trigger import dual_branch_workflow

    subtitle_path = tmp_path / "video.srt"
    video_path = tmp_path / "video.mp4"
    write_srt(subtitle_path)
    video_path.write_bytes(b"fake video")

    def fake_probe_video_duration_seconds(path: Path) -> float:
        assert path == video_path
        return 120.0

    def fake_extract_frames_at_timestamps(
        *,
        video_path: Path,
        output_dir: Path,
        timestamps_seconds: list[float],
        max_height: int,
    ) -> FrameExtractionResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "t_000000000.png").write_bytes(b"fake png")
        return FrameExtractionResult(backend="fake", frame_count=1)

    monkeypatch.setattr(dual_branch_workflow, "probe_video_duration_seconds", fake_probe_video_duration_seconds)
    monkeypatch.setattr(dual_branch_workflow, "extract_frames_at_timestamps", fake_extract_frames_at_timestamps)

    llm = FakeLlmClient(
        [
            {
                "plot_candidates": [
                    {
                        "candidate_type": "payback",
                        "start_time": 10.0,
                        "end_time": 22.0,
                        "trigger_time": 20.0,
                        "summary": "女主掀桌反击。",
                        "setup": "儿子被刁难。",
                        "turning_point": "女主掀桌。",
                        "payoff": "夺回主动权。",
                        "evidence": ["18.000-20.000 我今天就把桌子掀了"],
                    }
                ]
            },
            {
                "punchline_candidates": [
                    {
                        "start_time": 58.0,
                        "end_time": 64.0,
                        "trigger_time": 62.0,
                        "summary": "女主帮领导消毒形成笑点。",
                        "setup": "领导夸张担心。",
                        "punchline": "来嘛，我帮你消毒",
                        "payoff": "夸张和反制形成反差。",
                        "evidence": ["60.000-62.000 来嘛，我帮你消毒"],
                    }
                ]
            },
            {
                "triggerability_decisions": [
                    {
                        "candidate_id": "plot_demo_ep01_001",
                        "decision": "keep",
                        "expression_type": "爽点",
                        "importance_score": 0.92,
                        "start_time": 10.0,
                        "end_time": 22.0,
                        "trigger_time": 20.2,
                        "reason": "掀桌反击，爽感明确。",
                        "rank_reason": "强爽点。",
                    },
                    {
                        "candidate_id": "punchline_demo_ep01_001",
                        "decision": "keep",
                        "expression_type": "笑点",
                        "importance_score": 0.81,
                        "start_time": 58.0,
                        "end_time": 64.0,
                        "trigger_time": 62.2,
                        "reason": "包袱落地。",
                        "rank_reason": "清晰笑点。",
                    },
                ]
            },
        ]
    )

    pipeline = DualBranchExpressionTriggerPipeline(llm_client=llm, sample_interval_sec=30.0, top_k=4)

    result = pipeline.run(
        video_id="demo_ep01",
        video_file_path=video_path,
        subtitle_file_path=subtitle_path,
        metadata={"series": "demo"},
    )

    assert [candidate["candidate_id"] for candidate in result.plot_candidates] == ["plot_demo_ep01_001"]
    assert [candidate["candidate_id"] for candidate in result.punchline_candidates] == ["punchline_demo_ep01_001"]
    assert len(result.expression_candidates) == 2
    assert len(result.triggerability_decisions) == 2
    assert [trigger["expression_type"] for trigger in result.expression_triggers] == ["爽点", "笑点"]
    assert [trigger["trigger_time"] for trigger in result.expression_triggers] == [20.2, 62.2]
    assert result.resonance_cues == []
    assert len(llm.calls) == 3
    assert "Plot Beat Branch" in llm.calls[0]["user_prompt"]
    assert "Punchline Branch" in llm.calls[1]["user_prompt"]
    assert "Triggerability Judge" in llm.calls[2]["user_prompt"]
