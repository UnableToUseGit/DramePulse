from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.main import create_app
from services.api.repositories import admin_analysis
from services.api.scripts.init_local_dev import init_local_dev


class AdminAnalysisApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_env = {
            name: os.environ.get(name)
            for name in [
                "DRAMEPULSE_MODE",
                "SQLITE_PATH",
                "LOCAL_OSS_ROOT",
                "LOCAL_OSS_BUCKET",
                "VIDEO_ANALYZER_PYTHON",
                "VIDEO_ANALYZER_PROJECT",
                "VIDEO_ANALYZER_RESULT_ROOT",
                "VIDEO_ANALYZER_API_KEY",
                "VIDEO_ANALYZER_API_BASE",
                "VIDEO_ANALYZER_MODEL",
                "VIDEO_ANALYZER_MAX_FRAMES",
            ]
        }
        self.tmp_path = Path(self.tmpdir.name)
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["SQLITE_PATH"] = str(self.tmp_path / "dramepulse.sqlite")
        os.environ["LOCAL_OSS_ROOT"] = str(self.tmp_path)
        os.environ["LOCAL_OSS_BUCKET"] = "local"
        os.environ["VIDEO_ANALYZER_PYTHON"] = os.sys.executable
        os.environ["VIDEO_ANALYZER_PROJECT"] = str(self._write_fake_analyzer())
        os.environ["VIDEO_ANALYZER_RESULT_ROOT"] = str(self.tmp_path / "video-analyzer_result")
        os.environ["VIDEO_ANALYZER_API_KEY"] = "test-key"
        os.environ["VIDEO_ANALYZER_API_BASE"] = "https://example.test/v1"
        os.environ["VIDEO_ANALYZER_MODEL"] = "test-vision"
        os.environ["VIDEO_ANALYZER_MAX_FRAMES"] = "1"
        (self.tmp_path / "demo_video.mp4").write_bytes(b"0" * 2048)
        init_local_dev()
        self._insert_uploaded_video()
        self.client = TestClient(create_app())
        self._login_admin()

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def test_uploaded_video_defaults_to_not_started(self) -> None:
        response = self.client.get("/api/admin/series/beiwang")

        self.assertEqual(response.status_code, 200)
        episode = response.json()["episodes"][0]
        self.assertEqual(episode["analysis_status"], "not_started")
        self.assertIsNone(episode["analysis_job_id"])

    def test_analysis_job_completes_and_result_can_be_read(self) -> None:
        with patch.object(admin_analysis, "_ANALYSIS_SEMAPHORE", _ImmediateSemaphore()):
            response = self.client.post("/api/admin/videos/beiwang_ep01/analysis-jobs")

        self.assertEqual(response.status_code, 200)
        latest = self.client.get("/api/admin/videos/beiwang_ep01/analysis-jobs/latest").json()
        self.assertEqual(latest["status"], "completed")
        self.assertEqual(latest["stage"], "completed")
        self.assertTrue(Path(latest["result_text_path"]).is_file())
        self.assertEqual((self.tmp_path / "video-analyzer_result" / "beiwang" / "ep01.txt").read_text(encoding="utf-8"), "fake fusion")

        result = self.client.get("/api/admin/videos/beiwang_ep01/analysis-result")

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["content"], "fake fusion")

    def test_running_job_is_reused(self) -> None:
        admin_analysis.ensure_analysis_table()
        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            connection.execute(
                """
                INSERT INTO video_analysis_jobs (
                    job_id, video_id, status, stage, started_at
                )
                VALUES ('job_running', 'beiwang_ep01', 'running', 'running_video_analyzer', '2026-06-06 00:00:00')
                """
            )
            connection.commit()
        finally:
            connection.close()

        response = self.client.post("/api/admin/videos/beiwang_ep01/analysis-jobs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_id"], "job_running")
        connection = sqlite3.connect(self.tmp_path / "dramepulse.sqlite")
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM video_analysis_jobs WHERE video_id = ?",
                ("beiwang_ep01",),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 1)

    def test_failed_cli_marks_job_failed(self) -> None:
        os.environ["VIDEO_ANALYZER_PROJECT"] = str(self._write_fake_analyzer(exit_code=2))

        response = self.client.post("/api/admin/videos/beiwang_ep01/analysis-jobs")

        self.assertEqual(response.status_code, 200)
        latest = self.client.get("/api/admin/videos/beiwang_ep01/analysis-jobs/latest").json()
        self.assertEqual(latest["status"], "failed")
        self.assertIn("fake failure", latest["error_message"])

    def _login_admin(self) -> None:
        response = self.client.post(
            "/api/admin/auth/login",
            json={"username": "root", "password": "Dramepulse"},
        )
        self.assertEqual(response.status_code, 200)

    def _insert_uploaded_video(self) -> None:
        path = self.tmp_path / "dramas" / "beiwang" / "episodes" / "ep01" / "video.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"video")
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
                    "beiwang_ep01",
                    "beiwang",
                    "北望",
                    "北望 第1集",
                    1,
                    "ep01",
                    "local",
                    "dramas/beiwang/episodes/ep01/video.mp4",
                    "video/mp4",
                    path.stat().st_size,
                    "oss",
                    "active",
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def _write_fake_analyzer(self, *, exit_code: int = 0) -> Path:
        root = self.tmp_path / f"fake_analyzer_{exit_code}"
        package = root / "video_analyzer"
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "cli.py").write_text(
            textwrap.dedent(
                f"""
                from __future__ import annotations
                import argparse
                import sys
                from pathlib import Path

                parser = argparse.ArgumentParser()
                parser.add_argument("video_path")
                parser.add_argument("--output", required=True)
                parser.add_argument("--client")
                parser.add_argument("--api-key")
                parser.add_argument("--api-url")
                parser.add_argument("--model")
                parser.add_argument("--whisper-model")
                parser.add_argument("--max-frames")
                args = parser.parse_args()
                if {exit_code}:
                    print("fake failure", file=sys.stderr)
                    raise SystemExit({exit_code})
                output = Path(args.output)
                output.mkdir(parents=True, exist_ok=True)
                (output / "fusion_result.md").write_text("fake fusion", encoding="utf-8")
                (output / "analysis.json").write_text("{{}}", encoding="utf-8")
                """
            ),
            encoding="utf-8",
        )
        return root


class _ImmediateSemaphore:
    def __enter__(self) -> "_ImmediateSemaphore":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
