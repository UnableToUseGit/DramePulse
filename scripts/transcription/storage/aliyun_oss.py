from __future__ import annotations

from pathlib import Path

try:  # pragma: no cover
    import oss2  # type: ignore
except Exception:  # pragma: no cover
    oss2 = None  # type: ignore[assignment]

from ..config import AliyunOssConfig
from ..errors import ProviderExecutionError


class AliyunOssStore:
    def __init__(self, config: AliyunOssConfig) -> None:
        self.config = config
        missing = [
            name
            for name, value in [
                ("OSS_ENDPOINT", config.endpoint),
                ("OSS_BUCKET_NAME", config.bucket_name),
                ("OSS_ACCESS_KEY_ID", config.access_key_id),
                ("OSS_ACCESS_KEY_SECRET", config.access_key_secret),
            ]
            if not value
        ]
        if missing:
            raise ProviderExecutionError(f"OSS config is incomplete: {', '.join(missing)}")
        if oss2 is None:
            raise ProviderExecutionError("oss2 is not installed. Install it with: pip install oss2")
        auth = oss2.Auth(config.access_key_id, config.access_key_secret)
        self.bucket = oss2.Bucket(auth, config.endpoint, config.bucket_name)

    def upload_file(self, local_path: Path, object_key: str) -> str:
        self.bucket.put_object_from_file(object_key, str(local_path))
        return object_key

    def get_signed_download_url(self, object_key: str, expires: int | None = None) -> str:
        return str(
            self.bucket.sign_url(
                "GET",
                object_key,
                expires if expires is not None else self.config.signed_url_expires_sec,
            )
        )

    def delete_object(self, object_key: str) -> None:
        self.bucket.delete_object(object_key)
