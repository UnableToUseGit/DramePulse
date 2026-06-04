from fastapi.testclient import TestClient

from services.api.main import create_app


def test_append_home_feed_playback_logs(tmp_path, monkeypatch):
    from services.api.routers import dev_logs

    log_path = tmp_path / "home-feed-playback.log"
    monkeypatch.setattr(dev_logs, "HOME_FEED_PLAYBACK_LOG_PATH", log_path)
    client = TestClient(create_app())

    response = client.post(
        "/api/dev/home-feed-playback-logs",
        json={"lines": ["[HomeFeedPlayback] first", "[HomeFeedPlayback] second"]},
    )

    assert response.status_code == 200
    assert response.json() == {"written": 2, "path": str(log_path)}
    assert log_path.read_text(encoding="utf-8") == (
        "[HomeFeedPlayback] first\n[HomeFeedPlayback] second\n"
    )
