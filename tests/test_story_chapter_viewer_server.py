from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.story_chapter_viewer_server import discover_episodes, load_episode_detail, make_episode_id, write_chunk_safely


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

    def test_discover_episodes_finds_video_scene_and_chapter_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            episode_dir = root / "demo_series" / "ep01"
            episode_dir.mkdir(parents=True)
            (episode_dir / "video.mp4").write_bytes(b"video")
            (episode_dir / "scene_detection.json").write_text(
                json.dumps({"video_id": "scene_video_id", "scenes": []}),
                encoding="utf-8",
            )
            (episode_dir / "story_chapters.json").write_text(
                json.dumps({"story_chapters": []}),
                encoding="utf-8",
            )

            entries = discover_episodes(root)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].episode_id, "demo_series_ep01")
        self.assertEqual(entries[0].video_id, "scene_video_id")
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


if __name__ == "__main__":
    unittest.main()
