from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.scripts.import_new_assets import import_new_assets
from services.api.scripts.init_local_dev import init_local_dev


class NewAssetsImportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.previous_env = {
            name: os.environ.get(name)
            for name in ["DRAMEPULSE_MODE", "SQLITE_PATH", "LOCAL_OSS_ROOT", "LOCAL_OSS_BUCKET"]
        }
        shutil.copyfile(Path("apps/player-demo/assets/video/ep01.mp4"), self.tmp_path / "demo_video.mp4")
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["SQLITE_PATH"] = str(self.tmp_path / "dramepulse.sqlite")
        os.environ["LOCAL_OSS_ROOT"] = str(self.tmp_path)
        os.environ["LOCAL_OSS_BUCKET"] = "local"
        init_local_dev()
        self.sqlite_path = self.tmp_path / "dramepulse.sqlite"
        self._insert_video("naniandonzhi_ep01", "naniandonzhi", 1)

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def test_import_new_assets_and_expose_api(self) -> None:
        source_root = self.tmp_path / "NewAssets"
        self._write_plot_beats(source_root)
        self._write_interaction_assets(source_root)
        self._write_ads(source_root)

        dry_run = import_new_assets(source_root, apply=False)
        self.assertEqual(dry_run["plot_beats"]["matched"], 1)
        self.assertEqual(dry_run["interaction_assets"]["matched"], 2)
        self.assertEqual(dry_run["ad_slots"]["slot_count"], 1)
        self.assertEqual(dry_run["plot_beats"]["applied"], 0)

        applied = import_new_assets(source_root, apply=True)
        self.assertEqual(applied["plot_beats"]["applied"], 1)
        self.assertEqual(applied["interaction_assets"]["applied"], 2)
        self.assertEqual(applied["ad_slots"]["applied"], 1)

        connection = sqlite3.connect(self.sqlite_path)
        try:
            plot_count = connection.execute("SELECT COUNT(*) FROM plot_beats WHERE status = 'active'").fetchone()[0]
            interaction_count = connection.execute("SELECT COUNT(*) FROM video_interaction_items WHERE status = 'active'").fetchone()[0]
            ad_count = connection.execute("SELECT COUNT(*) FROM series_ad_slots WHERE status = 'active'").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(plot_count, 1)
        self.assertEqual(interaction_count, 2)
        self.assertEqual(ad_count, 1)

        client = TestClient(create_app())
        plot_response = client.get("/api/videos/naniandonzhi_ep01/plot-beats")
        self.assertEqual(plot_response.status_code, 200)
        self.assertEqual(plot_response.json()["plot_beats"][0]["beat_id"], "pb_001")

        raw_response = client.get("/api/videos/naniandonzhi_ep01/plot-beats/raw")
        self.assertEqual(raw_response.status_code, 200)
        self.assertIn("chapter_plot_beats", raw_response.json()["content"])

        interaction_response = client.get("/api/videos/naniandonzhi_ep01/interaction-assets?mode=inner_voice_danmaku")
        self.assertEqual(interaction_response.status_code, 200)
        self.assertEqual(interaction_response.json()["items"][0]["interaction_id"], "ivp_001")

        source_id_interaction_response = client.get("/api/videos/naniandongzhi_ep01/interaction-assets?mode=inner_voice_danmaku")
        self.assertEqual(source_id_interaction_response.status_code, 200)
        self.assertEqual(source_id_interaction_response.json()["video_id"], "naniandonzhi_ep01")
        self.assertEqual(source_id_interaction_response.json()["items"][0]["interaction_id"], "ivp_001")

        source_id_plot_response = client.get("/api/videos/naniandongzhi_ep01/plot-beats")
        self.assertEqual(source_id_plot_response.status_code, 200)
        self.assertEqual(source_id_plot_response.json()["video_id"], "naniandonzhi_ep01")

        ad_response = client.get("/api/series/beiwang/ad-slots")
        self.assertEqual(ad_response.status_code, 200)
        self.assertEqual(ad_response.json()["slots"][0]["ad"]["ad_id"], "ad_001")
        self.assertEqual(ad_response.json()["slots"][0]["ad"]["stream_url"], "/api/ads/ad_001/stream")

        alias_root = self.tmp_path / "AliasNewAssets"
        self._write_ads(alias_root, series_id="naniandonzhi")
        import_new_assets(alias_root, apply=True)
        alias_ad_response = client.get("/api/series/naniandongzhi/ad-slots")
        self.assertEqual(alias_ad_response.status_code, 200)
        self.assertEqual(alias_ad_response.json()["series_id"], "naniandonzhi")
        self.assertEqual(alias_ad_response.json()["slots"][0]["series_id"], "naniandonzhi")

        stream_response = client.get("/api/ads/ad_001/stream")
        self.assertEqual(stream_response.status_code, 200)
        self.assertEqual(stream_response.content, b"video")
        self.assertEqual(stream_response.headers["content-type"], "video/mp4")
        self.assertEqual(stream_response.headers["accept-ranges"], "bytes")

        range_response = client.get("/api/ads/ad_001/stream", headers={"Range": "bytes=1-3"})
        self.assertEqual(range_response.status_code, 206)
        self.assertEqual(range_response.content, b"ide")
        self.assertEqual(range_response.headers["content-range"], "bytes 1-3/5")

    def test_upload_interaction_assets_requires_admin_login(self) -> None:
        client = TestClient(create_app())

        response = client.post(
            "/api/admin/videos/naniandongzhi_ep01/interaction-assets",
            json=self._upload_interaction_assets_payload(),
        )

        self.assertEqual(response.status_code, 401)

    def test_upload_interaction_assets_rejects_missing_video(self) -> None:
        client = TestClient(create_app())
        self._login_admin(client)

        response = client.post(
            "/api/admin/videos/missing_ep01/interaction-assets",
            json=self._upload_interaction_assets_payload(),
        )

        self.assertEqual(response.status_code, 404)

    def test_upload_interaction_assets_replaces_existing_and_is_readable(self) -> None:
        source_root = self.tmp_path / "NewAssets"
        self._write_interaction_assets(source_root)
        import_new_assets(source_root, apply=True)
        client = TestClient(create_app())
        self._login_admin(client)

        response = client.post(
            "/api/admin/videos/naniandongzhi_ep01/interaction-assets",
            json=self._upload_interaction_assets_payload(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "video_id": "naniandonzhi_ep01",
                "interaction_mode": "inner_voice_danmaku",
                "uploaded_count": 1,
                "disabled_existing_count": 1,
                "active_count": 1,
            },
        )
        get_response = client.get("/api/videos/naniandongzhi_ep01/interaction-assets?mode=inner_voice_danmaku")
        items = get_response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["interaction_id"], "ivp_uploaded_001")
        self.assertEqual(items[0]["video_id"], "naniandonzhi_ep01")
        self.assertEqual(items[0]["interaction_mode"], "inner_voice_danmaku")
        self.assertEqual(items[0]["source_asset_id"], "admin_naniandonzhi_ep01_inner_voice_danmaku")
        self.assertEqual(items[0]["status"], "active")

    def test_upload_interaction_assets_without_replace_keeps_existing(self) -> None:
        source_root = self.tmp_path / "NewAssets"
        self._write_interaction_assets(source_root)
        import_new_assets(source_root, apply=True)
        client = TestClient(create_app())
        self._login_admin(client)
        payload = self._upload_interaction_assets_payload(replace_existing=False)

        response = client.post(
            "/api/admin/videos/naniandongzhi_ep01/interaction-assets",
            json=payload,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["disabled_existing_count"], 0)
        get_response = client.get("/api/videos/naniandongzhi_ep01/interaction-assets?mode=inner_voice_danmaku")
        self.assertEqual(
            {item["interaction_id"] for item in get_response.json()["items"]},
            {"ivp_001", "ivp_uploaded_001"},
        )

    def test_upload_interaction_assets_rejects_invalid_payload(self) -> None:
        client = TestClient(create_app())
        self._login_admin(client)
        payload = self._upload_interaction_assets_payload()
        payload["items"][0]["expire_time"] = 10.0

        response = client.post(
            "/api/admin/videos/naniandongzhi_ep01/interaction-assets",
            json=payload,
        )

        self.assertEqual(response.status_code, 422)

    def _insert_video(self, video_id: str, series_id: str, episode_no: int) -> None:
        connection = sqlite3.connect(self.sqlite_path)
        try:
            connection.execute(
                """
                INSERT INTO videos (
                    video_id, series_id, series_name, title, episode_no, episode_label,
                    oss_bucket, oss_object_key, content_type, size, source, status
                )
                VALUES (?, ?, '那年冬至', ?, ?, ?, 'local', ?, 'video/mp4', 1024, 'local', 'active')
                """,
                (video_id, series_id, f"那年冬至 第{episode_no}集", episode_no, f"ep{episode_no:02d}", f"{video_id}.mp4"),
            )
            connection.commit()
        finally:
            connection.close()

    def _write_plot_beats(self, root: Path) -> None:
        path = root / "plot_beat" / "naniandongzhi_ep01"
        path.mkdir(parents=True, exist_ok=True)
        payload = {
            "video_id": "naniandongzhi_ep01",
            "series_id": "naniandongzhi",
            "chapter_plot_beats": [
                {
                    "chapter_id": "ch_001",
                    "plot_beats": [
                        {
                            "beat_id": "pb_001",
                            "beat_type": "conflict_start",
                            "start_time": 1.0,
                            "end_time": 2.0,
                            "summary": "摘要",
                            "reason": "原因",
                        }
                    ],
                }
            ],
        }
        (path / "plot_beats.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        (path / "plot_beats.debug.json").write_text(json.dumps({"debug": True}, ensure_ascii=False), encoding="utf-8")

    def _write_interaction_assets(self, root: Path) -> None:
        emotional = root / "interaction_plan" / "emotional_button" / "naniandongzhi_ep01"
        emotional.mkdir(parents=True, exist_ok=True)
        (emotional / "interaction_plan.json").write_text(
            json.dumps(
                [
                    {
                        "interaction_id": "ip_001",
                        "trigger_time": 3.0,
                        "expire_time": 8.0,
                        "duration_sec": 5.0,
                        "content": {"expression_type": "笑点"},
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        inner_voice = root / "interaction_plan" / "inner_voice" / "naniandongzhi_ep01"
        inner_voice.mkdir(parents=True, exist_ok=True)
        (inner_voice / "interaction_plan.json").write_text(
            json.dumps(
                [
                    {
                        "interaction_id": "ivp_001",
                        "trigger_time": 10.0,
                        "expire_time": 18.0,
                        "duration_sec": 8.0,
                        "content": {"text": "我也想家了"},
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (inner_voice / "inner_voice_selection.json").write_text(json.dumps({"items": []}), encoding="utf-8")
        (inner_voice / "semantic_clusters.json").write_text(json.dumps({"clusters": []}), encoding="utf-8")

    def _write_ads(self, root: Path, *, series_id: str = "beiwang") -> None:
        path = root / "广告"
        path.mkdir(parents=True, exist_ok=True)
        (path / "ads.mp4").write_bytes(b"video")
        (path / "item.json").write_text(
            json.dumps(
                {
                    "series_id": series_id,
                    "slots": [
                        {
                            "slot_id": "beiwang_after_ep02_ad01",
                            "after_episode_no": 2,
                            "ad": {
                                "ad_id": "ad_001",
                                "video_url": "https://cdn.example.com/ads/ad_001.mp4",
                                "duration": 12,
                                "sponsor_label": "广告",
                                "product_name": "口红",
                                "selling_points": ["显气色"],
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _login_admin(self, client: TestClient) -> None:
        response = client.post(
            "/api/admin/auth/login",
            json={"username": "root", "password": "Dramepulse"},
        )
        self.assertEqual(response.status_code, 200)

    def _upload_interaction_assets_payload(self, *, replace_existing: bool = True) -> dict[str, object]:
        return {
            "interaction_mode": "inner_voice_danmaku",
            "replace_existing": replace_existing,
            "source_video_id": "ignored_source_video",
            "items": [
                {
                    "interaction_id": "ivp_uploaded_001",
                    "trigger_time": 12.0,
                    "expire_time": 20.0,
                    "duration_sec": 8.0,
                    "content": {"text": "Uploaded inner voice"},
                    "status": "disabled",
                }
            ],
        }


if __name__ == "__main__":
    unittest.main()
