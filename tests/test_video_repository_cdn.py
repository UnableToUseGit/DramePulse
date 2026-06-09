from __future__ import annotations

import os
import unittest

from services.api.repositories import videos


class VideoRepositoryCdnTest(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_env = {
            name: os.environ.get(name)
            for name in ["DRAMEPULSE_MODE", "SQLITE_PATH", "LOCAL_OSS_ROOT", "LOCAL_OSS_BUCKET", "CDN_BASE_URL"]
        }
        self.row = {
            "video_id": "ep_08",
            "series_id": "demo",
            "series_name": "Demo",
            "title": "\u7b2c8\u96c6",
            "episode_no": 8,
            "episode_label": "ep08",
            "duration": 120.0,
            "oss_bucket": "dramepulse",
            "oss_object_key": "\u77ed\u5267\u5408\u96c6/\u7b2c8\u96c6.mp4",
            "douyin_video_id": "123",
            "source": "oss",
        }
        self.episode_row = {
            **self.row,
            "video_id": "beiwang_ep01",
            "series_id": "beiwang",
            "episode_no": 1,
            "episode_label": "ep01",
            "oss_object_key": "dramas/beiwang/episodes/ep01/video.mp4",
        }

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_local_mode_uses_api_stream_url(self) -> None:
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["CDN_BASE_URL"] = "http://cdn.threekeyboardists.top"

        video = videos._to_video_response(self.row)

        self.assertEqual(video["stream_url"], "/api/videos/ep_08/stream")
        self.assertEqual(video["source"], "oss")

    def test_cloud_mode_with_cdn_uses_encoded_cdn_url(self) -> None:
        os.environ["DRAMEPULSE_MODE"] = "cloud"
        os.environ["CDN_BASE_URL"] = "http://cdn.threekeyboardists.top/"

        video = videos._to_video_response(self.row)

        self.assertEqual(
            video["stream_url"],
            "http://cdn.threekeyboardists.top/%E7%9F%AD%E5%89%A7%E5%90%88%E9%9B%86/%E7%AC%AC8%E9%9B%86.mp4",
        )
        self.assertEqual(video["stream_type"], "mp4")
        self.assertIsNone(video["hls_url"])
        self.assertEqual(
            video["mp4_url"],
            "http://cdn.threekeyboardists.top/%E7%9F%AD%E5%89%A7%E5%90%88%E9%9B%86/%E7%AC%AC8%E9%9B%86.mp4",
        )
        self.assertEqual(video["source"], "cdn")

    def test_cloud_mode_with_episode_hls_prefers_cdn_manifest(self) -> None:
        os.environ["DRAMEPULSE_MODE"] = "cloud"
        os.environ["CDN_BASE_URL"] = "http://cdn.threekeyboardists.top/"

        video = videos._to_video_response(self.episode_row)

        self.assertEqual(
            video["stream_url"],
            "http://cdn.threekeyboardists.top/dramas/beiwang/episodes/ep01/index.m3u8",
        )
        self.assertEqual(video["stream_type"], "hls")
        self.assertEqual(
            video["hls_url"],
            "http://cdn.threekeyboardists.top/dramas/beiwang/episodes/ep01/index.m3u8",
        )
        self.assertEqual(
            video["mp4_url"],
            "http://cdn.threekeyboardists.top/dramas/beiwang/episodes/ep01/video.mp4",
        )
        self.assertEqual(video["source"], "cdn")

    def test_cloud_mode_without_cdn_falls_back_to_api_stream_url(self) -> None:
        os.environ["DRAMEPULSE_MODE"] = "cloud"
        os.environ.pop("CDN_BASE_URL", None)

        video = videos._to_video_response(self.row)

        self.assertEqual(video["stream_url"], "/api/videos/ep_08/stream")
        self.assertEqual(video["stream_type"], "mp4")
        self.assertEqual(video["source"], "oss")

    def test_cloud_mode_without_cdn_uses_api_hls_manifest_for_episode_video(self) -> None:
        os.environ["DRAMEPULSE_MODE"] = "cloud"
        os.environ.pop("CDN_BASE_URL", None)

        video = videos._to_video_response(self.episode_row)

        self.assertEqual(video["stream_url"], "/api/videos/beiwang_ep01/hls/index.m3u8")
        self.assertEqual(video["stream_type"], "hls")
        self.assertEqual(video["hls_url"], "/api/videos/beiwang_ep01/hls/index.m3u8")
        self.assertEqual(video["mp4_url"], "/api/videos/beiwang_ep01/stream")
        self.assertEqual(video["source"], "oss")


if __name__ == "__main__":
    unittest.main()
