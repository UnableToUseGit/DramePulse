import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_api_base: str
    openai_model: str
    embedding_model: str
    chroma_dir: Path
    chroma_collection: str
    similarity_top_k: int


def get_settings(require_api_key: bool = True) -> Settings:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if require_api_key and not api_key:
        raise RuntimeError("OPENAI_API_KEY is required. Set it in the environment before running vediorag.")

    return Settings(
        openai_api_key=api_key,
        openai_api_base=os.getenv("OPENAI_API_BASE", "https://vip.auto-code.net/v1"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        chroma_dir=Path(os.getenv("CHROMA_DIR", str(PROJECT_ROOT / "data" / "chroma"))),
        chroma_collection=os.getenv("CHROMA_COLLECTION", "vediorag"),
        similarity_top_k=int(os.getenv("SIMILARITY_TOP_K", "8")),
    )
