from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.scripts.init_local_dev import init_local_dev


class AdminContentApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_env = {
            name: os.environ.get(name)
            for name in ["DRAMEPULSE_MODE", "SQLITE_PATH", "LOCAL_OSS_ROOT", "LOCAL_OSS_BUCKET"]
        }
        self.tmp_path = Path(self.tmpdir.name)
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["SQLITE_PATH"] = str(self.tmp_path / "dramepulse.sqlite")
        os.environ["LOCAL_OSS_ROOT"] = str(self.tmp_path)
        os.environ["LOCAL_OSS_BUCKET"] = "local"
        (self.tmp_path / "demo_video.mp4").write_bytes(b"0" * 2048)
        init_local_dev()
        self.client = TestClient(create_app())
        self._login_admin()

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def _login_admin(self) -> None:
        response = self.client.post(
            "/api/admin/auth/login",
            json={"username": "root", "password": "Dramepulse"},
        )
        self.assertEqual(response.status_code, 200)

    def test_create_series_writes_name_txt(self) -> None:
        response = self.client.post(
            "/api/admin/series",
            json={"series_id": "tianxiadiyiwanku", "series_name": "天下第一纨绔"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name_object_key"], "dramas/tianxiadiyiwanku/name.txt")
        self.assertEqual(
            (self.tmp_path / "dramas" / "tianxiadiyiwanku" / "name.txt").read_text(encoding="utf-8"),
            "天下第一纨绔",
        )

    def test_create_series_updates_existing_video_series_name(self) -> None:
        self._insert_video("tianxiadiyiwanku_ep01", "tianxiadiyiwanku", None, 1)

        response = self.client.post(
            "/api/admin/series",
            json={"series_id": "tianxiadiyiwanku", "series_name": "天下第一纨绔"},
        )

        self.assertEqual(response.status_code, 200)
        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            row = connection.execute(
                "SELECT series_name FROM videos WHERE video_id = ?",
                ("tianxiadiyiwanku_ep01",),
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(row[0], "天下第一纨绔")

    def test_list_and_detail_series_return_existing_episodes(self) -> None:
        self._insert_video("tianxiadiyiwanku_ep01", "tianxiadiyiwanku", "天下第一纨绔", 1)
        self._insert_video("tianxiadiyiwanku_ep02", "tianxiadiyiwanku", "天下第一纨绔", 2)

        self._insert_video("legacy_ep01", "legacy", "Legacy", 1, "raw/legacy/ep01/video.mp4")

        list_response = self.client.get("/api/admin/series")
        detail_response = self.client.get("/api/admin/series/tianxiadiyiwanku")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        series_items = list_response.json()["series"]
        series = next(item for item in series_items if item["series_id"] == "tianxiadiyiwanku")
        self.assertNotIn("legacy", {item["series_id"] for item in series_items})
        self.assertEqual(series["series_id"], "tianxiadiyiwanku")
        self.assertEqual(series["series_name"], "天下第一纨绔")
        self.assertEqual(series["episode_count"], 2)
        self.assertEqual(series["name_object_key"], "dramas/tianxiadiyiwanku/name.txt")
        detail = detail_response.json()
        self.assertEqual(detail["series"]["episode_count"], 2)
        self.assertEqual([episode["episode_label"] for episode in detail["episodes"]], ["ep01", "ep02"])

    def test_delete_series_marks_videos_inactive_without_removing_oss_file(self) -> None:
        self._insert_video("tianxiadiyiwanku_ep01", "tianxiadiyiwanku", "demo", 1)
        object_path = self.tmp_path / "dramas" / "tianxiadiyiwanku" / "episodes" / "ep01" / "video.mp4"
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(b"video")

        response = self.client.delete("/api/admin/series/tianxiadiyiwanku")
        list_response = self.client.get("/api/admin/series")
        videos_response = self.client.get("/api/videos")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_episode_count"], 1)
        listed = next(item for item in list_response.json()["series"] if item["series_id"] == "tianxiadiyiwanku")
        self.assertEqual(listed["status"], "deleted")
        self.assertNotIn("tianxiadiyiwanku_ep01", {item["video_id"] for item in videos_response.json()["videos"]})
        self.assertTrue(object_path.exists())
        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            status_value = connection.execute(
                "SELECT status FROM videos WHERE video_id = ?",
                ("tianxiadiyiwanku_ep01",),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(status_value, "deleted")

    def test_restore_series_marks_videos_active_again(self) -> None:
        self._insert_video("tianxiadiyiwanku_ep01", "tianxiadiyiwanku", "demo", 1)
        self.client.delete("/api/admin/series/tianxiadiyiwanku")

        response = self.client.post("/api/admin/series/tianxiadiyiwanku/restore")
        list_response = self.client.get("/api/admin/series")
        videos_response = self.client.get("/api/videos")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["restored_episode_count"], 1)
        listed = next(item for item in list_response.json()["series"] if item["series_id"] == "tianxiadiyiwanku")
        self.assertEqual(listed["status"], "active")
        self.assertIn("tianxiadiyiwanku_ep01", {item["video_id"] for item in videos_response.json()["videos"]})

    def test_delete_series_rejects_missing_series(self) -> None:
        response = self.client.delete("/api/admin/series/missing")

        self.assertEqual(response.status_code, 404)

    def test_rejects_invalid_series_id(self) -> None:
        response = self.client.post("/api/admin/series", json={"series_id": "天下第一纨绔", "series_name": "天下第一纨绔"})

        self.assertEqual(response.status_code, 422)

    def test_upload_cover_writes_expected_object_key(self) -> None:
        response = self.client.post(
            "/api/admin/series/tianxiadiyiwanku/cover",
            files={"file": ("cover.jpg", b"image-bytes", "image/jpeg")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["object_key"], "dramas/tianxiadiyiwanku/cover.jpg")
        self.assertEqual((self.tmp_path / "dramas" / "tianxiadiyiwanku" / "cover.jpg").read_bytes(), b"image-bytes")

    def test_rejects_non_image_cover(self) -> None:
        response = self.client.post(
            "/api/admin/series/tianxiadiyiwanku/cover",
            files={"file": ("cover.txt", b"not-image", "text/plain")},
        )

        self.assertEqual(response.status_code, 415)

    def test_upload_episode_writes_video_and_upserts_videos_table(self) -> None:
        response = self.client.post(
            "/api/admin/series/tianxiadiyiwanku/episodes",
            data={"series_name": "天下第一纨绔", "episode_no": "1", "title": "天下第一纨绔 第1集"},
            files={"video": ("video.mp4", b"video-bytes", "video/mp4")},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["video_id"], "tianxiadiyiwanku_ep01")
        self.assertEqual(payload["object_key"], "dramas/tianxiadiyiwanku/episodes/ep01/video.mp4")
        self.assertEqual(
            (self.tmp_path / "dramas" / "tianxiadiyiwanku" / "episodes" / "ep01" / "video.mp4").read_bytes(),
            b"video-bytes",
        )

        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            row = connection.execute(
                """
                SELECT video_id, series_id, series_name, title, episode_no, episode_label, oss_object_key, size
                FROM videos
                WHERE video_id = ?
                """,
                ("tianxiadiyiwanku_ep01",),
            ).fetchone()
        finally:
            connection.close()

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row[1], "tianxiadiyiwanku")
        self.assertEqual(row[2], "天下第一纨绔")
        self.assertEqual(row[3], "天下第一纨绔 第1集")
        self.assertEqual(row[4], 1)
        self.assertEqual(row[5], "ep01")
        self.assertEqual(row[6], "dramas/tianxiadiyiwanku/episodes/ep01/video.mp4")
        self.assertEqual(row[7], len(b"video-bytes"))

    def test_upload_episode_chunks_writes_video_and_upserts_videos_table(self) -> None:
        first = self.client.post(
            "/api/admin/series/tianxiadiyiwanku/episodes/chunks",
            data={
                "series_name": "天下第一纨绔",
                "episode_no": "1",
                "title": "天下第一纨绔 第1集",
                "upload_id": "upload123",
                "chunk_index": "0",
                "total_chunks": "2",
                "total_size": "11",
            },
            files={"chunk": ("ep01.00000.part", b"video-", "application/octet-stream")},
        )
        second = self.client.post(
            "/api/admin/series/tianxiadiyiwanku/episodes/chunks",
            data={
                "series_name": "天下第一纨绔",
                "episode_no": "1",
                "title": "天下第一纨绔 第1集",
                "upload_id": "upload123",
                "chunk_index": "1",
                "total_chunks": "2",
                "total_size": "11",
            },
            files={"chunk": ("ep01.00001.part", b"bytes", "application/octet-stream")},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        payload = second.json()
        self.assertEqual(payload["video_id"], "tianxiadiyiwanku_ep01")
        self.assertEqual(payload["object_key"], "dramas/tianxiadiyiwanku/episodes/ep01/video.mp4")
        self.assertEqual(
            (self.tmp_path / "dramas" / "tianxiadiyiwanku" / "episodes" / "ep01" / "video.mp4").read_bytes(),
            b"video-bytes",
        )
        self.assertFalse((self.tmp_path / ".dramepulse_uploads" / "upload123.part").exists())

        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            row = connection.execute(
                """
                SELECT video_id, oss_object_key, size
                FROM videos
                WHERE video_id = ?
                """,
                ("tianxiadiyiwanku_ep01",),
            ).fetchone()
        finally:
            connection.close()

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row[1], "dramas/tianxiadiyiwanku/episodes/ep01/video.mp4")
        self.assertEqual(row[2], len(b"video-bytes"))

    def test_rejects_non_video_episode_upload(self) -> None:
        response = self.client.post(
            "/api/admin/series/tianxiadiyiwanku/episodes",
            data={"series_name": "天下第一纨绔", "episode_no": "1", "title": "天下第一纨绔 第1集"},
            files={"video": ("video.txt", b"not-video", "text/plain")},
        )

        self.assertEqual(response.status_code, 415)

    def test_upload_episode_danmaku_writes_json_and_imports_items(self) -> None:
        self._insert_video("tianxiadiyiwanku_ep01", "tianxiadiyiwanku", "天下第一纨绔", 1)
        payload = {
            "danmaku": {
                "items": [
                    {"danmaku_id": "a", "time_sec": 1.2, "text": "第一条", "digg_count": 3, "score": 0.5},
                    {"danmaku_id": "b", "time_sec": 2.5, "text": "第二条"},
                ]
            }
        }

        response = self.client.post(
            "/api/admin/series/tianxiadiyiwanku/episodes/ep01/danmaku",
            files={"file": ("douyin.json", json.dumps(payload).encode("utf-8"), "application/json")},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["object_key"], "dramas/tianxiadiyiwanku/episodes/ep01/danmaku/douyin.json")
        self.assertEqual(body["danmaku_count"], 2)
        self.assertEqual(
            json.loads(
                (self.tmp_path / "dramas" / "tianxiadiyiwanku" / "episodes" / "ep01" / "danmaku" / "douyin.json").read_text(
                    encoding="utf-8"
                )
            ),
            payload,
        )

        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            video_row = connection.execute(
                "SELECT douyin_json_path FROM videos WHERE video_id = ?",
                ("tianxiadiyiwanku_ep01",),
            ).fetchone()
            count = connection.execute(
                "SELECT COUNT(*) FROM danmaku_items WHERE video_id = ?",
                ("tianxiadiyiwanku_ep01",),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(video_row[0], "dramas/tianxiadiyiwanku/episodes/ep01/danmaku/douyin.json")
        self.assertEqual(count, 2)

    def test_rejects_invalid_episode_danmaku_json(self) -> None:
        self._insert_video("tianxiadiyiwanku_ep01", "tianxiadiyiwanku", "天下第一纨绔", 1)

        response = self.client.post(
            "/api/admin/series/tianxiadiyiwanku/episodes/ep01/danmaku",
            files={"file": ("douyin.json", b"{bad json", "application/json")},
        )

        self.assertEqual(response.status_code, 422)

    def _insert_video(
        self,
        video_id: str,
        series_id: str,
        series_name: str | None,
        episode_no: int,
        object_key: str | None = None,
    ) -> None:
        episode_label = f"ep{episode_no:02d}"
        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            connection.execute(
                """
                INSERT INTO videos (
                    video_id, series_id, series_name, title, episode_no, episode_label,
                    oss_bucket, oss_object_key, content_type, size, source, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    series_id,
                    series_name,
                    f"{series_name or series_id} 第{episode_no}集",
                    episode_no,
                    episode_label,
                    "local",
                    object_key or f"dramas/{series_id}/episodes/{episode_label}/video.mp4",
                    "video/mp4",
                    123,
                    "oss",
                    "active",
                ),
            )
            connection.commit()
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
