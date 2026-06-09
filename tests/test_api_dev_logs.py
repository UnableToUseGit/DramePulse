from fastapi.testclient import TestClient

from services.api.main import create_app


def test_append_home_feed_playback_logs(tmp_path, monkeypatch):
    client = TestClient(create_app())

    response = client.post(
        "/api/dev/home-feed-playback-logs",
        json={"lines": ["[HomeFeedPlayback] first", "[HomeFeedPlayback] second"]},
    )

    assert response.status_code == 404
