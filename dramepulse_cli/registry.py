from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib import import_module


Runner = Callable[[list[str]], int]


@dataclass(frozen=True)
class PipelineCommand:
    name: str
    title: str
    summary: str
    module: str
    example_args: list[str]
    outputs: list[str]
    runner: Runner | None = None

    def run(self, argv: Sequence[str]) -> int:
        if self.runner is not None:
            return self.runner(list(argv))
        module = import_module(self.module)
        main = getattr(module, "main", None)
        if not callable(main):
            raise RuntimeError(f"Pipeline module has no callable main(): {self.module}")
        try:
            result = main(list(argv))
        except SystemExit as exc:
            if isinstance(exc.code, int):
                return exc.code
            return 1
        return int(result or 0)


PIPELINES: tuple[PipelineCommand, ...] = (
    PipelineCommand(
        name="video-preprocess",
        title="Video Preprocess",
        summary="对输入视频完成音频抽取、字幕转录和镜头切分，产出后续算法可复用的基础资产。",
        module="scripts.video_preprocess.run_pipeline",
        example_args=[
            "data/case1/ep01.mp4",
            "--video-id",
            "case1_ep01",
            "--output-root",
            "output/video_preprocess",
        ],
        outputs=[
            "audio/<video_id>.16k-mono.wav",
            "transcription/<video_id>.srt",
            "scene_detection/scene_detection.json",
            "video_preprocess_manifest.json",
        ],
    ),
    PipelineCommand(
        name="expression-trigger",
        title="Expression Trigger",
        summary="从字幕和视频帧生成表达触发点资产，用于播放器内即时互动。",
        module="scripts.expression_trigger.run_workflow_batch",
        example_args=[
            "--data-root",
            "data",
            "--output-root",
            "output/workflow_expression_trigger",
            "--video-id",
            "case1_ep01",
        ],
        outputs=["expression_triggers.json", "expression_triggers.debug.json"],
    ),
    PipelineCommand(
        name="story-chapter",
        title="Story Chapter",
        summary="基于字幕、场景切分和稀疏抽帧生成剧情章节资产。",
        module="scripts.story_chapter.run_subtitle_scene_aligned",
        example_args=[
            "case1_ep01",
            "--video",
            "data/case1/ep01.mp4",
            "--transcription",
            "output/transcription/case1_ep01.transcription.json",
            "--scene-detection",
            "output/scene_detection/case1_ep01/scene_detection.json",
        ],
        outputs=["story_chapters.json", "story_chapters.debug.json"],
    ),
    PipelineCommand(
        name="plot-beat",
        title="Plot Beat",
        summary="基于剧情章节、字幕和章节内抽帧生成原子剧情节拍资产。",
        module="scripts.plot_beat.run_chapter_aligned_batch",
        example_args=[
            "--data-root",
            "data",
            "--story-chapter-root",
            "output/story_chapter",
            "--output-root",
            "output/plot_beat/chapter_aligned",
            "--video-id",
            "case1_ep01",
        ],
        outputs=["plot_beats.json", "plot_beats.debug.json"],
    ),
    PipelineCommand(
        name="inner-voice-danmaku",
        title="Inner Voice Danmaku",
        summary="从真实弹幕 CSV 聚类、筛选候选语义，并生成心里话弹幕互动方案。",
        module="scripts.inner_voice_danmaku.run_batch",
        example_args=[
            "--series-id",
            "case1",
            "--episode-ids",
            "ep01",
            "--csv-path",
            "data/danmaku.csv",
        ],
        outputs=["semantic_clusters.json", "inner_voice_selection.json", "interaction_plan.json"],
    ),
    PipelineCommand(
        name="highlight-commerce",
        title="Highlight Commerce",
        summary="从剧情高光素材生成高光带货脚本、卡通参考图和 Seedance 竖屏广告视频。",
        module="scripts.highlight_commerce.run_v2_pipeline",
        example_args=[
            "--asset",
            "data/role-commerce-v2/highlight_commerce_case1.json",
            "--output-root",
            "output/role-commerce-v2",
        ],
        outputs=[
            "highlight_commerce_script.json",
            "highlight_commerce_cartoon_asset.json",
            "highlight_commerce_v2_result.json",
        ],
    ),
)


def get_pipeline(name: str, registry: Sequence[PipelineCommand] = PIPELINES) -> PipelineCommand | None:
    for pipeline in registry:
        if pipeline.name == name:
            return pipeline
    return None
