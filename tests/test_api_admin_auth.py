from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from services.api.admin_auth import ADMIN_SESSION_COOKIE
from services.api.main import create_app
from services.api.scripts.init_local_dev import init_local_dev


class AdminAuthApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_env = {
            name: os.environ.get(name)
            for name in ["DRAMEPULSE_MODE", "SQLITE_PATH", "LOCAL_OSS_ROOT", "LOCAL_OSS_BUCKET"]
        }
        tmp_path = Path(self.tmpdir.name)
        os.environ["DRAMEPULSE_MODE"] = "local"
        os.environ["SQLITE_PATH"] = str(tmp_path / "dramepulse.sqlite")
        os.environ["LOCAL_OSS_ROOT"] = str(tmp_path)
        os.environ["LOCAL_OSS_BUCKET"] = "local"
        (tmp_path / "demo_video.mp4").write_bytes(b"0" * 2048)
        init_local_dev()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmpdir.cleanup()

    def test_admin_dashboard_requires_login(self) -> None:
        response = self.client.get("/api/admin/dashboard")

        self.assertEqual(response.status_code, 401)

    def test_login_rejects_invalid_credentials(self) -> None:
        response = self.client.post(
            "/api/admin/auth/login",
            json={"username": "root", "password": "wrong"},
        )

        self.assertEqual(response.status_code, 401)

    def test_login_sets_cookie_and_allows_admin_api(self) -> None:
        login_response = self.client.post(
            "/api/admin/auth/login",
            json={"username": "root", "password": "Dramepulse"},
        )
        dashboard_response = self.client.get("/api/admin/dashboard")

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json(), {"authenticated": True, "username": "root", "role": "admin"})
        self.assertIn(ADMIN_SESSION_COOKIE, self.client.cookies)
        self.assertEqual(dashboard_response.status_code, 200)

    def test_readonly_user_can_read_but_cannot_write(self) -> None:
        login_response = self.client.post(
            "/api/admin/auth/login",
            json={"username": "user", "password": "123"},
        )
        dashboard_response = self.client.get("/api/admin/dashboard")
        series_response = self.client.get("/api/admin/series")
        write_response = self.client.post(
            "/api/admin/series",
            json={"series_id": "readonly_demo", "series_name": "Readonly Demo"},
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json(), {"authenticated": True, "username": "user", "role": "readonly"})
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(series_response.status_code, 200)
        self.assertEqual(write_response.status_code, 403)

    def test_logout_clears_admin_access(self) -> None:
        self.client.post("/api/admin/auth/login", json={"username": "root", "password": "Dramepulse"})

        logout_response = self.client.post("/api/admin/auth/logout")
        dashboard_response = self.client.get("/api/admin/dashboard")

        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(dashboard_response.status_code, 401)

    def test_me_reports_auth_state(self) -> None:
        anonymous_response = self.client.get("/api/admin/auth/me")
        self.client.post("/api/admin/auth/login", json={"username": "root", "password": "Dramepulse"})
        authenticated_response = self.client.get("/api/admin/auth/me")

        self.assertEqual(anonymous_response.json(), {"authenticated": False, "username": None, "role": None})
        self.assertEqual(authenticated_response.json(), {"authenticated": True, "username": "root", "role": "admin"})


if __name__ == "__main__":
    unittest.main()
