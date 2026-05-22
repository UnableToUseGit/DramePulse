from __future__ import annotations

import unittest

from services.api.oss_client import parse_range_header
from services.api.scripts.import_oss_videos import make_video_id, parse_episode_no


class ApiOssClientTest(unittest.TestCase):
    def test_parse_regular_range(self) -> None:
        parsed = parse_range_header("bytes=0-1023", 10_000)
        assert parsed is not None
        self.assertEqual(parsed.start, 0)
        self.assertEqual(parsed.end, 1023)

    def test_parse_open_ended_range(self) -> None:
        parsed = parse_range_header("bytes=100-", 150)
        assert parsed is not None
        self.assertEqual(parsed.start, 100)
        self.assertEqual(parsed.end, 149)

    def test_parse_suffix_range(self) -> None:
        parsed = parse_range_header("bytes=-50", 1_000)
        assert parsed is not None
        self.assertEqual(parsed.start, 950)
        self.assertEqual(parsed.end, 999)

    def test_parse_range_rejects_unsatisfiable_request(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsatisfiable"):
            parse_range_header("bytes=1000-1001", 100)

    def test_make_video_id_from_chinese_episode_name(self) -> None:
        self.assertEqual(make_video_id("第10集.mp4"), "ep_10")
        self.assertEqual(parse_episode_no("第10集.mp4"), 10)

    def test_make_video_id_from_generic_name(self) -> None:
        self.assertEqual(make_video_id("clips/demo video.mp4"), "oss_demo_video")
        self.assertIsNone(parse_episode_no("clips/demo video.mp4"))


if __name__ == "__main__":
    unittest.main()
