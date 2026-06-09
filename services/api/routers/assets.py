from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from ..oss_client import get_object_meta, read_object_range

router = APIRouter()
root_router = APIRouter()


def _is_public_asset_key(object_key: str) -> bool:
    if object_key.startswith("storyboards/"):
        return True
    parts = object_key.split("/")
    return (
        len(parts) == 3
        and parts[0] == "dramas"
        and parts[2].lower() in {"cover.jpg", "cover.jpeg", "cover.png", "cover.webp"}
    )


def _read_public_asset(object_key: str) -> Response:
    clean_key = object_key.strip().lstrip("/")
    if not clean_key or not _is_public_asset_key(clean_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    try:
        meta = get_object_meta(clean_key)
        body = read_object_range(clean_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found") from exc
    except Exception as exc:
        if exc.__class__.__name__ == "NoSuchKey":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found") from exc
        raise

    return Response(
        content=body,
        media_type=meta.content_type,
        headers={"Content-Length": str(meta.content_length), "Content-Disposition": "inline"},
    )


@router.get("/assets/{object_key:path}")
def retrieve_public_asset(object_key: str) -> Response:
    return _read_public_asset(object_key)


@root_router.get("/storyboards/{asset_path:path}")
def retrieve_legacy_storyboard_asset(asset_path: str) -> Response:
    return _read_public_asset(f"storyboards/{asset_path}")
