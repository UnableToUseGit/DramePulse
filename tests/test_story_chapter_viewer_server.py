from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.story_chapter.viewer_server import (
    build_story_chapter_annotation,
    discover_episodes,
    load_episode_detail,
    make_episode_id,
    save_story_chapter_annotation,
    write_chunk_safely,
)


class StoryChapterViewerServerTest(unittest.TestCase):
    def test_write_chunk_safely_treats_broken_pipe_as_client_disconnect(self) -> None:
        class ClosedWriter:
            def write(self, chunk: bytes) -> None:
                raise BrokenPipeError("client closed")

        self.assertFalse(write_chunk_safely(ClosedWriter(), b"chunk"))

    def test_write_chunk_safely_writes_active_socket(self) -> None:
        class OpenWriter:
            def __init__(self) -> None:
                self.chunks: list[bytes] = []

            def write(self, chunk: bytes) -> None:
                self.chunks.append(chunk)

        writer = OpenWriter()

        self.assertTrue(write_chunk_safely(writer, b"chunk"))
        self.assertEqual(writer.chunks, [b"chunk"])

    def test_make_episode_id_joins_series_and_episode(self) -> None:
        self.assertEqual(make_episode_id("demo_series", "ep01"), "demo_series_ep01")

    def test_discover_episodes_uses_directory_video_id_for_legacy_scene_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            episode_dir = root / "jialijiawai" / "ep01"
            episode_dir.mkdir(parents=True)
            (episode_dir / "video.mp4").write_bytes(b"video")
            (episode_dir / "scene_detection.json").write_text(
                json.dumps({"video_id": "jiali_jiawai_ep01", "scenes": []}),
                encoding="utf-8",
            )
            (episode_dir / "story_chapters.json").write_text(
                json.dumps({"story_chapters": []}),
                encoding="utf-8",
            )

            entries = discover_episodes(root)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].episode_id, "jialijiawai_ep01")
        self.assertEqual(entries[0].video_id, "jialijiawai_ep01")
        self.assertTrue(entries[0].has_chapters)

    def test_discover_episodes_uses_external_chapter_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "dataset"
            output_root = Path(tmpdir) / "output"
            episode_dir = root / "demo_series" / "ep02"
            episode_dir.mkdir(parents=True)
            (episode_dir / "video.mp4").write_bytes(b"video")
            (episode_dir / "scene_detection.json").write_text(
                json.dumps({"video_id": "demo_series_ep02", "scenes": []}),
                encoding="utf-8",
            )
            chapter_dir = output_root / "demo_series_ep02"
            chapter_dir.mkdir(parents=True)
            (chapter_dir / "story_chapters.json").write_text(
                json.dumps({"story_chapters": [{"chapter_id": "ch_001"}]}),
                encoding="utf-8",
            )

            entries = discover_episodes(root, chapter_output_root=output_root)

        self.assertTrue(entries[0].has_chapters)
        self.assertEqual(entries[0].chapter_path, output_root / "demo_series_ep02" / "story_chapters.json")

    def test_load_episode_detail_returns_scenes_chapters_and_media_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            episode_dir = root / "demo_series" / "ep01"
            episode_dir.mkdir(parents=True)
            (episode_dir / "video.mp4").write_bytes(b"video")
            (episode_dir / "scene_detection.json").write_text(
                json.dumps(
                    {
                        "video_id": "demo_series_ep01",
                        "scenes": [{"scene_id": "s1", "start_time": 0, "end_time": 3}],
                    }
                ),
                encoding="utf-8",
            )
            (episode_dir / "story_chapters.json").write_text(
                json.dumps(
                    {
                        "story_chapters": [
                            {
                                "chapter_id": "ch1",
                                "start_time": 0,
                                "end_time": 3,
                                "title": "开场",
                                "summary": "故事开始。",
                                "importance": 0.5,
                            }
                        ],
                        "warnings": ["sample warning"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            entry = discover_episodes(root)[0]

            detail = load_episode_detail(entry)

        self.assertEqual(detail["episode_id"], "demo_series_ep01")
        self.assertEqual(detail["media_url"], "/media/demo_series_ep01/video.mp4")
        self.assertEqual(len(detail["scenes"]), 1)
        self.assertEqual(detail["chapters"][0]["title"], "开场")
        self.assertEqual(detail["warnings"], ["sample warning"])

    def test_load_episode_detail_reads_warnings_from_debug_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            episode_dir = root / "demo_series" / "ep01"
            episode_dir.mkdir(parents=True)
            (episode_dir / "video.mp4").write_bytes(b"video")
            (episode_dir / "scene_detection.json").write_text(
                json.dumps(
                    {
                        "video_id": "demo_series_ep01",
                        "scenes": [{"scene_id": "s1", "start_time": 0, "end_time": 3}],
                    }
                ),
                encoding="utf-8",
            )
            (episode_dir / "story_chapters.json").write_text(
                json.dumps(
                    {
                        "video_id": "demo_series_ep01",
                        "series_id": "demo_series",
                        "story_chapters": [
                            {
                                "chapter_id": "ch1",
                                "start_time": 0,
                                "end_time": 3,
                                "title": "开场",
                                "summary": "故事开始。",
                                "reason": "开场事件完整。",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (episode_dir / "story_chapters.debug.json").write_text(
                json.dumps({"warnings": ["debug warning"]}, ensure_ascii=False),
                encoding="utf-8",
            )
            entry = discover_episodes(root)[0]

            detail = load_episode_detail(entry)

        self.assertEqual(detail["chapters"][0]["title"], "开场")
        self.assertEqual(detail["warnings"], ["debug warning"])

    def test_build_story_chapter_annotation_attaches_boundary_summary_to_ending_chapter(self) -> None:
        annotation = build_story_chapter_annotation(
            video_id="demo_ep01",
            duration_seconds=30.0,
            payload={
                "final_chapter_summary": "最后一章自动结束。",
                "boundaries": [
                    {"time": 20.0, "ending_chapter_summary": "进入结尾事件。"},
                    {"time": 10.0, "ending_chapter_summary": "进入主要冲突。"},
                    {"time": 30.0, "ending_chapter_summary": "末尾边界会被过滤。"},
                    {"time": 0.0, "ending_chapter_summary": "开头边界会被过滤。"},
                ]
            },
        )

        self.assertEqual(
            annotation["boundaries"],
            [
                {"time": 10.0, "ending_chapter_summary": "进入主要冲突。"},
                {"time": 20.0, "ending_chapter_summary": "进入结尾事件。"},
            ],
        )
        self.assertEqual(
            [(chapter["start_time"], chapter["end_time"]) for chapter in annotation["chapters"]],
            [(0.0, 10.0), (10.0, 20.0), (20.0, 30.0)],
        )
        self.assertEqual(annotation["chapters"][0]["summary"], "进入主要冲突。")
        self.assertEqual(annotation["chapters"][1]["summary"], "进入结尾事件。")
        self.assertEqual(annotation["chapters"][2]["summary"], "最后一章自动结束。")
        self.assertEqual(annotation["final_chapter_summary"], "最后一章自动结束。")
        self.assertNotIn("boundary_reason", annotation["chapters"][0])

    def test_save_story_chapter_annotation_writes_gold_annotation_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "dataset"
            annotation_root = Path(tmpdir) / "annotations"
            episode_dir = root / "demo_series" / "ep01"
            episode_dir.mkdir(parents=True)
            (episode_dir / "video.mp4").write_bytes(b"video")
            (episode_dir / "scene_detection.json").write_text(
                json.dumps(
                    {
                        "video_id": "demo_video_ep01",
                        "scenes": [{"scene_id": "s1", "start_time": 0, "end_time": 30}],
                    }
                ),
                encoding="utf-8",
            )
            entry = discover_episodes(root, annotation_root=annotation_root)[0]

            result = save_story_chapter_annotation(
                entry,
                annotation_root,
                {
                    "boundaries": [{"time": 12.5, "ending_chapter_summary": "冲突升级。"}],
                    "final_chapter_summary": "冲突后的收束。",
                },
            )

            expected_path = annotation_root / "demo_series_ep01.annotation.json"
            self.assertEqual(result["path"], str(expected_path))
            self.assertTrue(expected_path.exists())
            saved = json.loads(expected_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["boundaries"], [{"time": 12.5, "ending_chapter_summary": "冲突升级。"}])
            self.assertEqual(
                [(chapter["start_time"], chapter["end_time"]) for chapter in saved["chapters"]],
                [(0.0, 12.5), (12.5, 30.0)],
            )
            self.assertEqual(saved["chapters"][1]["summary"], "冲突后的收束。")


if __name__ == "__main__":
    unittest.main()
