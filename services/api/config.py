from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

try:  # pragma: no cover
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]


def _load_env_file() -> None:
    if load_dotenv is None:
        return
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env")


def _getenv(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    mode: str
    sqlite_path: Path
    local_oss_root: Path
    local_oss_bucket: str
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    mysql_ssl: bool
    oss_endpoint: str
    oss_bucket: str
    oss_access_key_id: str
    oss_access_key_secret: str
    oss_region: str
    openai_api_key: str
    openai_api_base: str
    openai_model: str
    openai_embedding_model: str
    chroma_dir: Path
    chroma_collection: str
    similarity_top_k: int

    @property
    def oss_endpoint_url(self) -> str:
        if self.oss_endpoint.startswith(("http://", "https://")):
            return self.oss_endpoint
        return f"https://{self.oss_endpoint}"


def get_settings() -> Settings:
    _load_env_file()
    repo_root = Path(__file__).resolve().parents[2]
    return Settings(
        mode=_getenv("DRAMEPULSE_MODE", "local").lower(),
        sqlite_path=repo_root / _getenv("SQLITE_PATH", "dramepulse.sqlite"),
        local_oss_root=repo_root / _getenv("LOCAL_OSS_ROOT", "."),
        local_oss_bucket=_getenv("LOCAL_OSS_BUCKET", "local"),
        mysql_host=_getenv("MYSQL_HOST"),
        mysql_port=int(_getenv("MYSQL_PORT", "3306")),
        mysql_user=_getenv("MYSQL_USER"),
        mysql_password=_getenv("MYSQL_PASSWORD"),
        mysql_database=_getenv("MYSQL_DATABASE", "dramepulse"),
        mysql_ssl=_getenv("MYSQL_SSL", "false").lower() in {"1", "true", "yes"},
        oss_endpoint=_getenv("OSS_ENDPOINT"),
        oss_bucket=_getenv("OSS_BUCKET") or _getenv("OSS_BUCKET_NAME"),
        oss_access_key_id=_getenv("OSS_ACCESS_KEY_ID"),
        oss_access_key_secret=_getenv("OSS_ACCESS_KEY_SECRET"),
        oss_region=_getenv("OSS_REGION", "cn-beijing"),
        openai_api_key=_getenv("OPENAI_API_KEY"),
        openai_api_base=_getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        openai_model=_getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openai_embedding_model=_getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        chroma_dir=repo_root / _getenv("CHROMA_DIR", "data/chroma"),
        chroma_collection=_getenv("CHROMA_COLLECTION", "dramepulse_story_qa"),
        similarity_top_k=int(_getenv("SIMILARITY_TOP_K", "8")),
    )


def require_complete_cloud_settings(settings: Settings) -> None:
    missing = [
        name
        for name, value in [
            ("MYSQL_HOST", settings.mysql_host),
            ("MYSQL_USER", settings.mysql_user),
            ("MYSQL_PASSWORD", settings.mysql_password),
            ("MYSQL_DATABASE", settings.mysql_database),
            ("OSS_ENDPOINT", settings.oss_endpoint),
            ("OSS_BUCKET", settings.oss_bucket),
            ("OSS_ACCESS_KEY_ID", settings.oss_access_key_id),
            ("OSS_ACCESS_KEY_SECRET", settings.oss_access_key_secret),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def require_complete_settings(settings: Settings) -> None:
    if settings.mode == "cloud":
        require_complete_cloud_settings(settings)
