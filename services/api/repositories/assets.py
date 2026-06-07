from __future__ import annotations

from urllib.parse import quote

from ..config import get_settings


def public_object_url(object_key: str) -> str:
    settings = get_settings()
    clean_key = object_key.strip().lstrip("/")
    if settings.mode == "cloud" and settings.cdn_base_url:
        return f"{settings.cdn_base_url.rstrip('/')}/{quote(clean_key, safe='/')}"
    return f"/api/assets/{quote(clean_key, safe='/')}"
