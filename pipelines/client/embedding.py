from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable, Protocol

from openai import OpenAI
import requests


ProgressCallback = Callable[[str, dict[str, Any]], None]


class EmbeddingClientProtocol(Protocol):
    last_call_diagnostics: dict[str, Any]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class CachedEmbeddingClient:
    def __init__(
        self,
        *,
        inner_client: EmbeddingClientProtocol,
        cache_path: Path,
        model_name: str,
    ) -> None:
        self.inner_client = inner_client
        self.cache_path = cache_path
        self.model_name = model_name
        self.last_call_diagnostics: dict[str, Any] = {}
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.cache_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    cache_key TEXT PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    text TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_embedding_cache_model_name ON embedding_cache(model_name)"
            )

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(f"{self.model_name}\n{text}".encode("utf-8")).hexdigest()
        return digest

    def _load_cached_vectors(self, texts: list[str]) -> dict[str, list[float]]:
        if not texts:
            return {}
        keys = [self._cache_key(text) for text in texts]
        placeholders = ",".join("?" for _key in keys)
        with sqlite3.connect(self.cache_path) as connection:
            rows = connection.execute(
                f"SELECT cache_key, vector_json FROM embedding_cache WHERE cache_key IN ({placeholders})",
                keys,
            ).fetchall()
        cached: dict[str, list[float]] = {}
        for cache_key, vector_json in rows:
            parsed = json.loads(vector_json)
            if isinstance(parsed, list):
                cached[str(cache_key)] = [float(value) for value in parsed]
        return cached

    def _store_vectors(self, texts: list[str], vectors: list[list[float]]) -> None:
        now = time.time()
        rows = [
            (
                self._cache_key(text),
                self.model_name,
                text,
                json.dumps(vector, ensure_ascii=False),
                now,
            )
            for text, vector in zip(texts, vectors, strict=True)
        ]
        with sqlite3.connect(self.cache_path) as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO embedding_cache
                (cache_key, model_name, text, vector_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        started_at = time.perf_counter()
        cached_by_key = self._load_cached_vectors(texts)
        vectors_by_key = dict(cached_by_key)
        missing_texts: list[str] = []
        seen_missing_keys: set[str] = set()
        for text in texts:
            key = self._cache_key(text)
            if key in vectors_by_key or key in seen_missing_keys:
                continue
            seen_missing_keys.add(key)
            missing_texts.append(text)

        inner_diagnostics: dict[str, Any] = {}
        if missing_texts:
            missing_vectors = self.inner_client.embed_texts(missing_texts)
            self._store_vectors(missing_texts, missing_vectors)
            for text, vector in zip(missing_texts, missing_vectors, strict=True):
                vectors_by_key[self._cache_key(text)] = vector
            diagnostics = getattr(self.inner_client, "last_call_diagnostics", {})
            if isinstance(diagnostics, dict):
                inner_diagnostics = dict(diagnostics)

        result = [vectors_by_key[self._cache_key(text)] for text in texts]
        self.last_call_diagnostics = {
            "provider": "cache",
            "model": self.model_name,
            "cache_path": str(self.cache_path),
            "input_count": len(texts),
            "cache_hits": len(texts) - len(missing_texts),
            "cache_misses": len(missing_texts),
            "elapsed_sec": round(time.perf_counter() - started_at, 3),
            "inner": inner_diagnostics,
        }
        return result


class OpenAICompatibleEmbeddingClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout_sec: int = 90,
        batch_size: int = 128,
    ) -> None:
        self.api_key = api_key or os.environ.get("EMBEDDING_API_KEY") or os.environ.get("API_KEY", "")
        self.base_url = base_url or os.environ.get("EMBEDDING_BASE_URL") or os.environ.get("BASE_URL") or None
        self.model_name = model_name or os.environ.get("EMBEDDING_MODEL") or os.environ.get("MODEL") or "baai/bge-m3"
        self.timeout_sec = timeout_sec
        self.batch_size = max(1, int(batch_size))
        self.last_call_diagnostics: dict[str, Any] = {}
        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout_sec,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        started_at = time.perf_counter()
        vectors: list[list[float]] = []
        usage_payload: dict[str, int] = {}
        request_count = 0
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            response = self._client.embeddings.create(model=self.model_name, input=batch)
            request_count += 1
            vectors.extend(list(item.embedding) for item in response.data)
            usage = getattr(response, "usage", None)
            if usage is not None:
                for key in ("prompt_tokens", "total_tokens"):
                    value = getattr(usage, key, None)
                    if value is not None:
                        usage_payload[key] = usage_payload.get(key, 0) + int(value)
        self.last_call_diagnostics = {
            "provider": "openai_compatible",
            "model": self.model_name,
            "input_count": len(texts),
            "batch_size": self.batch_size,
            "request_count": request_count,
            "elapsed_sec": round(time.perf_counter() - started_at, 3),
            "usage": usage_payload,
        }
        return vectors


class OpenRouterEmbeddingClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        url: str | None = None,
        model_name: str | None = None,
        timeout_sec: int = 90,
        batch_size: int = 128,
        site_url: str | None = None,
        site_name: str | None = None,
        requests_module: Any = requests,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("EMBEDDING_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("API_KEY", "")
        self.url = url or os.environ.get("EMBEDDING_BASE_URL") or "https://openrouter.ai/api/v1/embeddings"
        self.model_name = model_name or os.environ.get("EMBEDDING_MODEL") or os.environ.get("MODEL") or "baai/bge-m3"
        self.timeout_sec = timeout_sec
        self.batch_size = max(1, int(batch_size))
        self.site_url = site_url or os.environ.get("OPENROUTER_SITE_URL") or os.environ.get("EMBEDDING_SITE_URL")
        self.site_name = site_name or os.environ.get("OPENROUTER_SITE_NAME") or os.environ.get("EMBEDDING_SITE_NAME")
        self._requests = requests_module
        self.progress_callback = progress_callback
        self.last_call_diagnostics: dict[str, Any] = {}

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-OpenRouter-Title"] = self.site_name
        return headers

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        started_at = time.perf_counter()
        vectors: list[list[float]] = []
        usage_payload: dict[str, int] = {}
        request_count = 0
        batch_count = (len(texts) + self.batch_size - 1) // self.batch_size
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            response = self._requests.post(
                url=self.url,
                headers=self._headers(),
                json={
                    "model": self.model_name,
                    "input": batch,
                    "encoding_format": "float",
                },
                timeout=self.timeout_sec,
            )
            request_count += 1
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, list):
                raise ValueError("OpenRouter embedding response missing data list")
            for item in data:
                if not isinstance(item, dict) or "embedding" not in item:
                    raise ValueError("OpenRouter embedding response has invalid data item")
                vectors.append([float(value) for value in item["embedding"]])
            usage = payload.get("usage") if isinstance(payload, dict) else None
            if isinstance(usage, dict):
                for key in ("prompt_tokens", "total_tokens"):
                    value = usage.get(key)
                    if value is not None:
                        usage_payload[key] = usage_payload.get(key, 0) + int(value)
            if self.progress_callback is not None:
                batch_usage = usage if isinstance(usage, dict) else {}
                self.progress_callback(
                    "embedding_batch",
                    {
                        "batch_index": request_count,
                        "batch_count": batch_count,
                        "batch_size": len(batch),
                        "total_tokens": batch_usage.get("total_tokens"),
                    },
                )
        self.last_call_diagnostics = {
            "provider": "openrouter",
            "model": self.model_name,
            "input_count": len(texts),
            "batch_size": self.batch_size,
            "request_count": request_count,
            "elapsed_sec": round(time.perf_counter() - started_at, 3),
            "usage": usage_payload,
        }
        return vectors
