from __future__ import annotations

import re
from pathlib import PurePosixPath

from services.api.config import get_settings, require_complete_settings
from services.api.db import db_cursor
from services.api.oss_client import get_bucket


def make_video_id(object_key: str) -> str:
    stem = PurePosixPath(object_key).stem
    match = re.search(r"第\s*(\d+)\s*集", stem)
    if match:
        return f"ep_{int(match.group(1)):02d}"
    normalized = re.sub(r"[^0-9A-Za-z]+", "_", stem).strip("_").lower()
    return f"oss_{normalized}" if normalized else "oss_video"


def parse_episode_no(object_key: str) -> int | None:
    match = re.search(r"第\s*(\d+)\s*集", PurePosixPath(object_key).stem)
    return int(match.group(1)) if match else None


def make_title(object_key: str) -> str:
    return PurePosixPath(object_key).stem


def import_oss_videos() -> int:
    settings = get_settings()
    require_complete_settings(settings)
    bucket = get_bucket(settings)
    imported = 0
    for obj in bucket.list_objects().object_list:
        object_key = obj.key
        if not object_key.lower().endswith(".mp4"):
            continue
        video_id = make_video_id(object_key)
        with db_cursor(settings) as cursor:
            cursor.execute(
                """
                INSERT INTO videos (
                    video_id,
                    title,
                    episode_no,
                    oss_bucket,
                    oss_object_key,
                    content_type,
                    size,
                    source,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'oss', 'active')
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    episode_no = VALUES(episode_no),
                    content_type = VALUES(content_type),
                    size = VALUES(size),
                    source = VALUES(source),
                    status = VALUES(status)
                """,
                (
                    video_id,
                    make_title(object_key),
                    parse_episode_no(object_key),
                    settings.oss_bucket,
                    object_key,
                    "video/mp4",
                    int(obj.size),
                ),
            )
        imported += 1
    return imported


if __name__ == "__main__":
    count = import_oss_videos()
    print(f"Imported {count} OSS video objects.")
