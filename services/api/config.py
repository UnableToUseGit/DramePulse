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
    cdn_base_url: str
    openai_api_key: str
    openai_api_base: str
    openai_model: str
    openai_embedding_model: str
    chroma_dir: Path
    chroma_collection: str
    similarity_top_k: int
    story_qa_backend: str
    lightrag_working_root: Path
    lightrag_working_dir: Path
    lightrag_query_mode: str
    lightrag_enable_rerank: bool
    lightrag_top_k: int
    lightrag_chunk_top_k: int
    lightrag_cosine_threshold: float
    lightrag_max_entity_tokens: int
    lightrag_max_relation_tokens: int
    lightrag_max_total_tokens: int
    lightrag_response_type: str
    lightrag_embedding_model: str
    lightrag_embedding_dim: int
    lightrag_embedding_api_base: str
    lightrag_embedding_api_key: str
    lightrag_embedding_send_dim: bool
    watch_assistant_asr_backend: str
    watch_assistant_asr_model: str
    watch_assistant_asr_max_bytes: int

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
        cdn_base_url=_getenv("CDN_BASE_URL"),
        openai_api_key=_getenv("OPENAI_API_KEY"),
        openai_api_base=_getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        openai_model=_getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openai_embedding_model=_getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        chroma_dir=repo_root / _getenv("CHROMA_DIR", "data/chroma"),
        chroma_collection=_getenv("CHROMA_COLLECTION", "dramepulse_story_qa"),
        similarity_top_k=int(_getenv("SIMILARITY_TOP_K", "8")),
        story_qa_backend=_getenv("STORY_QA_BACKEND", "chroma").lower(),
        lightrag_working_root=repo_root / _getenv("LIGHTRAG_WORKING_ROOT", "data/story_qa"),
        lightrag_working_dir=repo_root / _getenv(
            "LIGHTRAG_WORKING_DIR",
            "data/story_qa/demo-drama/episode-001/lightrag",
        ),
        lightrag_query_mode=_getenv("LIGHTRAG_QUERY_MODE", "hybrid"),
        lightrag_enable_rerank=_getenv("LIGHTRAG_ENABLE_RERANK", "false").lower() in {"1", "true", "yes"},
        lightrag_top_k=int(_getenv("LIGHTRAG_TOP_K", "20")),
        lightrag_chunk_top_k=int(_getenv("LIGHTRAG_CHUNK_TOP_K", "10")),
        lightrag_cosine_threshold=float(_getenv("LIGHTRAG_COSINE_THRESHOLD", "0.0")),
        lightrag_max_entity_tokens=int(_getenv("LIGHTRAG_MAX_ENTITY_TOKENS", "6000")),
        lightrag_max_relation_tokens=int(_getenv("LIGHTRAG_MAX_RELATION_TOKENS", "8000")),
        lightrag_max_total_tokens=int(_getenv("LIGHTRAG_MAX_TOTAL_TOKENS", "30000")),
        lightrag_response_type=_getenv("LIGHTRAG_RESPONSE_TYPE", "一句话短回答，最多60个中文字，不要引用来源，不要输出References，不要输出思考过程"),
        lightrag_embedding_model=_getenv("LIGHTRAG_EMBEDDING_MODEL", _getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")),
        lightrag_embedding_dim=int(_getenv("LIGHTRAG_EMBEDDING_DIM", "1536")),
        lightrag_embedding_api_base=_getenv("LIGHTRAG_EMBEDDING_API_BASE", _getenv("OPENAI_API_BASE", "https://api.openai.com/v1")),
        lightrag_embedding_api_key=_getenv("LIGHTRAG_EMBEDDING_API_KEY", _getenv("OPENAI_API_KEY")),
        lightrag_embedding_send_dim=_getenv("LIGHTRAG_EMBEDDING_SEND_DIM", "false").lower() in {"1", "true", "yes"},
        watch_assistant_asr_backend=_getenv("WATCH_ASSISTANT_ASR_BACKEND", "mock").lower(),
        watch_assistant_asr_model=_getenv("WATCH_ASSISTANT_ASR_MODEL", "whisper-1"),
        watch_assistant_asr_max_bytes=int(_getenv("WATCH_ASSISTANT_ASR_MAX_BYTES", str(2 * 1024 * 1024))),
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
