from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .env import get_env_value


@dataclass(frozen=True)
class AliyunAsrConfig:
    api_base: str = "https://dashscope.aliyuncs.com/api/v1"
    model: str = "fun-asr"
    language_hints: list[str] = field(default_factory=lambda: ["zh", "en"])
    diarization_enabled: bool = True
    api_key: str | None = None
    api_key_env: str = "ALIYUN_API_KEY"
    poll_interval_sec: float = 2.0
    poll_timeout_sec: float = 900.0


@dataclass(frozen=True)
class AliyunOssConfig:
    endpoint: str | None = None
    bucket_name: str | None = None
    access_key_id: str | None = None
    access_key_secret: str | None = None
    access_key_id_env: str = "OSS_ACCESS_KEY_ID"
    access_key_secret_env: str = "OSS_ACCESS_KEY_SECRET"
    object_prefix: str = "audio/"
    signed_url_expires_sec: int = 3600
    retain_remote_artifacts: bool = False


@dataclass(frozen=True)
class AliyunTranscriberConfig:
    asr: AliyunAsrConfig = field(default_factory=AliyunAsrConfig)
    oss: AliyunOssConfig = field(default_factory=AliyunOssConfig)

    @classmethod
    def from_env(cls, *, env_path: Path | None = None) -> "AliyunTranscriberConfig":
        return cls(
            asr=AliyunAsrConfig(
                api_key=get_env_value("ALIYUN_API_KEY", env_path=env_path)
                or get_env_value("DASHSCOPE_API_KEY", env_path=env_path),
            ),
            oss=AliyunOssConfig(
                endpoint=get_env_value("OSS_ENDPOINT", env_path=env_path),
                bucket_name=get_env_value("OSS_BUCKET_NAME", env_path=env_path),
                access_key_id=get_env_value("OSS_ACCESS_KEY_ID", env_path=env_path),
                access_key_secret=get_env_value("OSS_ACCESS_KEY_SECRET", env_path=env_path),
            ),
        )
