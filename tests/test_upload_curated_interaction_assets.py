from __future__ import annotations

import json
from pathlib import Path


def test_build_upload_payloads_groups_by_interaction_mode() -> None:
    from scripts.upload_curated_interaction_assets import build_upload_payloads_for_video

    payloads = build_upload_payloads_for_video(
        video_id="beiwang_ep01",
        plan=[
            {
                "interaction_id": "ivp_beiwang_ep01_001",
                "video_id": "beiwang_ep01",
                "series_id": "beiwang",
                "episode_no": 1,
                "interaction_mode": "inner_voice_danmaku",
                "trigger_time": 21.23456,
                "duration_sec": 8.0,
                "expire_time": 29.23456,
                "content": {"text": "这人真会演", "candidate_id": "ivcluster_beiwang_ep01_001"},
            },
            {
                "interaction_id": "ip_beiwang_ep01_001",
                "video_id": "beiwang_ep01",
                "series_id": "beiwang",
                "episode_no": 1,
                "interaction_mode": "emotional_button",
                "trigger_time": 12.2,
                "duration_sec": 5.0,
                "expire_time": 17.2,
                "content": {"expression_type": "爽点", "source_trigger_id": "et_beiwang_ep01_001"},
            },
        ],
    )

    assert [payload["interaction_mode"] for payload in payloads] == ["emotional_button", "inner_voice_danmaku"]
    emotional_payload = payloads[0]
    assert emotional_payload["source_video_id"] == "beiwang_ep01"
    assert emotional_payload["source_series_id"] == "beiwang"
    assert emotional_payload["canonical_series_id"] == "beiwang"
    assert emotional_payload["episode_no"] == 1
    assert emotional_payload["asset_id"] == "ia_beiwang_ep01_emotional_button"
    assert emotional_payload["replace_existing"] is True
    assert emotional_payload["items"] == [
        {
            "interaction_id": "ip_beiwang_ep01_001",
            "trigger_time": 12.2,
            "expire_time": 17.2,
            "duration_sec": 5.0,
            "content": {"expression_type": "爽点", "source_trigger_id": "et_beiwang_ep01_001"},
            "status": "active",
        }
    ]
    assert payloads[1]["items"][0]["trigger_time"] == 21.235


def test_build_upload_payloads_can_override_canonical_series_id() -> None:
    from scripts.upload_curated_interaction_assets import build_upload_payloads_for_video

    payloads = build_upload_payloads_for_video(
        video_id="jialijiawai_ep02",
        canonical_series_id="canonical_jialijiawai",
        replace_existing=False,
        plan=[
            {
                "interaction_id": "ip_jialijiawai_ep02_001",
                "interaction_mode": "emotional_button",
                "trigger_time": 1,
                "duration_sec": 5,
                "content": {},
            }
        ],
    )

    assert payloads[0]["source_series_id"] == "jialijiawai"
    assert payloads[0]["canonical_series_id"] == "canonical_jialijiawai"
    assert payloads[0]["episode_no"] == 2
    assert payloads[0]["replace_existing"] is False


def test_discover_video_ids_from_curated_root(tmp_path: Path) -> None:
    from scripts.upload_curated_interaction_assets import discover_video_ids

    for video_id in ["beiwang_ep01", "beiwang_ep02"]:
        plan_path = tmp_path / video_id / "interaction_plan.json"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text("[]\n", encoding="utf-8")
    (tmp_path / "beiwang_ep03").mkdir()

    assert discover_video_ids(tmp_path) == ["beiwang_ep01", "beiwang_ep02"]
    assert discover_video_ids(tmp_path, video_ids=["beiwang_ep03", "beiwang_ep01"]) == ["beiwang_ep01", "beiwang_ep03"]


def test_load_curated_plan(tmp_path: Path) -> None:
    from scripts.upload_curated_interaction_assets import load_curated_plan

    plan_path = tmp_path / "beiwang_ep01" / "interaction_plan.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(json.dumps([{"interaction_id": "ip_001"}, "bad"]), encoding="utf-8")

    assert load_curated_plan(tmp_path, "beiwang_ep01") == [{"interaction_id": "ip_001"}]


def test_build_upload_url_encodes_video_id() -> None:
    from scripts.upload_curated_interaction_assets import build_upload_url

    assert (
        build_upload_url("http://39.96.219.88:8000/", "beiwang_ep01")
        == "http://39.96.219.88:8000/api/admin/videos/beiwang_ep01/interaction-assets"
    )
    assert (
        build_upload_url("http://example.test/base", "series/ep01")
        == "http://example.test/base/api/admin/videos/series%2Fep01/interaction-assets"
    )


def test_load_cookie_header_from_netscape_file(tmp_path: Path) -> None:
    from scripts.upload_curated_interaction_assets import load_cookie_header

    cookies_path = tmp_path / "cookies.txt"
    cookies_path.write_text(
        "\n".join(
            [
                "# Netscape HTTP Cookie File",
                ".example.test\tTRUE\t/\tFALSE\t2147483647\tsessionid\tabc123",
                "#HttpOnly_.example.test\tTRUE\t/\tFALSE\t2147483647\tcsrftoken\txyz",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert load_cookie_header(cookies_path) == "sessionid=abc123; csrftoken=xyz"


def test_load_cookie_header_strips_quoted_netscape_cookie_value(tmp_path: Path) -> None:
    from scripts.upload_curated_interaction_assets import load_cookie_header

    cookies_path = tmp_path / "cookies.txt"
    cookies_path.write_text(
        ".example.test\tTRUE\t/\tFALSE\t2147483647\tdramepulse_admin_session\t\"abc123==\"\n",
        encoding="utf-8",
    )

    assert load_cookie_header(cookies_path) == "dramepulse_admin_session=abc123=="


def test_load_cookie_header_rejects_expired_netscape_cookies(tmp_path: Path) -> None:
    from scripts.upload_curated_interaction_assets import load_cookie_header

    cookies_path = tmp_path / "cookies.txt"
    cookies_path.write_text(
        ".example.test\tTRUE\t/\tFALSE\t100\tdramepulse_admin_session\tabc123\n",
        encoding="utf-8",
    )

    try:
        load_cookie_header(cookies_path, now_epoch=101)
    except ValueError as exc:
        assert "expired cookies" in str(exc)
    else:
        raise AssertionError("expected expired cookie error")


def test_load_cookie_header_from_direct_cookie_header(tmp_path: Path) -> None:
    from scripts.upload_curated_interaction_assets import load_cookie_header

    cookies_path = tmp_path / "cookies.txt"
    cookies_path.write_text("Cookie: sessionid=abc123; csrftoken=xyz\n", encoding="utf-8")

    assert load_cookie_header(cookies_path) == "sessionid=abc123; csrftoken=xyz"
