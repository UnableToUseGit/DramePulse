from __future__ import annotations

from dataclasses import dataclass
import re

import oss2

from .config import Settings, get_settings, require_complete_settings


@dataclass(frozen=True)
class OssObjectMeta:
    content_length: int
    content_type: str
    last_modified: int | None = None


@dataclass(frozen=True)
class ParsedRange:
    start: int
    end: int


def get_bucket(settings: Settings | None = None, bucket_name: str | None = None) -> oss2.Bucket:
    resolved = settings or get_settings()
    require_complete_settings(resolved)
    auth = oss2.Auth(resolved.oss_access_key_id, resolved.oss_access_key_secret)
    return oss2.Bucket(auth, resolved.oss_endpoint_url, bucket_name or resolved.oss_bucket)


def get_object_meta(object_key: str, bucket_name: str | None = None) -> OssObjectMeta:
    result = get_bucket(bucket_name=bucket_name).head_object(object_key)
    return OssObjectMeta(
        content_length=int(result.headers.get("Content-Length", "0")),
        content_type=str(result.headers.get("Content-Type", "video/mp4")),
        last_modified=int(result.headers["Last-Modified"]) if str(result.headers.get("Last-Modified", "")).isdigit() else None,
    )


def parse_range_header(range_header: str | None, total_size: int) -> ParsedRange | None:
    if not range_header:
        return None
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
    if not match:
        raise ValueError("Invalid Range header")
    start_text, end_text = match.groups()
    if not start_text and not end_text:
        raise ValueError("Invalid Range header")
    if start_text:
        start = int(start_text)
        end = int(end_text) if end_text else total_size - 1
    else:
        suffix_length = int(end_text)
        if suffix_length <= 0:
            raise ValueError("Invalid Range header")
        start = max(total_size - suffix_length, 0)
        end = total_size - 1
    if start >= total_size or end < start:
        raise ValueError("Unsatisfiable Range header")
    return ParsedRange(start=start, end=min(end, total_size - 1))


def read_object_range(object_key: str, start: int | None = None, end: int | None = None, bucket_name: str | None = None) -> bytes:
    bucket = get_bucket(bucket_name=bucket_name)
    if start is None or end is None:
        return bucket.get_object(object_key).read()
    return bucket.get_object(object_key, byte_range=(start, end)).read()
