from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import http.client
import shutil
import time
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import requests

from ..base import ArtifactStore
from ..chunking import prepare_audio_for_transcription, split_audio_by_duration
from ..config import AliyunAsrConfig, AliyunTranscriberConfig
from ..errors import ProviderExecutionError
from ..logging_utils import format_elapsed_minutes_seconds, log_transcription_event
from ..types import TranscriptSegment, TranscriptionRequest, TranscriptionResult

try:  # pragma: no cover
    from ..storage.aliyun_oss import AliyunOssStore
except Exception:  # pragma: no cover
    AliyunOssStore = None  # type: ignore[assignment]


def parse_aliyun_transcription_result(raw_result: dict[str, Any]) -> list[TranscriptSegment]:
    transcript_items = raw_result.get("transcripts") or []
    if not transcript_items:
        return []
    sentences = transcript_items[0].get("sentences") or []
    segments: list[TranscriptSegment] = []
    for sentence in sentences:
        text = str(sentence.get("text", "")).strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start=float(sentence.get("begin_time", 0)) / 1000.0,
                end=float(sentence.get("end_time", 0)) / 1000.0,
                text=text,
            )
        )
    return segments


class AliyunAsrClient:
    result_download_attempts = 5
    result_download_timeout = (10, 300)

    def __init__(self, config: AliyunAsrConfig):
        self.config = config

    @staticmethod
    def _is_instance_pool_exhausted(message: object) -> bool:
        return "instance pool exhausted" in str(message or "").lower()

    @staticmethod
    def _is_no_words_response(result: dict[str, Any]) -> bool:
        code = str(result.get("code") or "").strip()
        message = str(result.get("message") or "").strip()
        return code == "ASR_RESPONSE_HAVE_NO_WORDS" or message == "ASR_RESPONSE_HAVE_NO_WORDS"

    def _download_transcription_result(self, transcription_url: str) -> dict[str, Any]:
        host = urlparse(transcription_url).netloc or "<unknown>"
        last_error: Exception | None = None
        for attempt in range(1, self.result_download_attempts + 1):
            started = time.perf_counter()
            try:
                response = requests.get(
                    transcription_url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "VideoChatWorkflow/1.0",
                    },
                    timeout=self.result_download_timeout,
                    allow_redirects=True,
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
            except ValueError as exc:
                raise ProviderExecutionError("Failed to parse Aliyun transcription result JSON") from exc

            if attempt < self.result_download_attempts:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                log_transcription_event(
                    "aliyun_transcription_result_download_retrying",
                    provider="aliyun",
                    host=host,
                    attempt=attempt,
                    max_attempts=self.result_download_attempts,
                    elapsed_ms=elapsed_ms,
                    error_type=type(last_error).__name__ if last_error else "",
                    error=str(last_error),
                )
                time.sleep(min(2 ** (attempt - 1), 8))

        raise ProviderExecutionError(
            f"Failed to download Aliyun transcription result from {host} "
            f"after {self.result_download_attempts} attempts: {last_error}"
        ) from last_error

    def transcribe_from_url(self, file_url: str) -> list[TranscriptSegment]:
        return parse_aliyun_transcription_result(self.transcribe_raw_from_url(file_url))

    def transcribe_raw_from_url(self, file_url: str) -> dict[str, Any]:
        try:
            import dashscope
            from dashscope.audio.asr import Transcription
        except ImportError as exc:
            raise ProviderExecutionError("dashscope is not installed. Install it with: pip install dashscope") from exc

        api_key = self.config.api_key
        if not api_key:
            raise ProviderExecutionError("Aliyun API key is not configured.")

        dashscope.base_http_api_url = self.config.api_base
        dashscope.api_key = api_key

        task_response = Transcription.async_call(
            model=self.config.model,
            file_urls=[file_url],
            language_hints=list(self.config.language_hints),
            diarization_enabled=self.config.diarization_enabled,
        )
        if task_response.status_code != HTTPStatus.OK:
            raise ProviderExecutionError(f"Failed to submit Aliyun transcription task: {task_response.message}")

        task_id = task_response.output.task_id
        exhausted_retries = 0
        start_time = time.time()
        while True:
            if time.time() - start_time > self.config.poll_timeout_sec:
                raise ProviderExecutionError(
                    f"Aliyun transcription timed out after {self.config.poll_timeout_sec}s"
                )

            transcription_response = Transcription.wait(task=task_id)
            if transcription_response.status_code != HTTPStatus.OK:
                raise ProviderExecutionError(f"Aliyun transcription failed: {transcription_response.message}")

            results = transcription_response.output.get("results", [])
            for result in results:
                if result.get("subtask_status") == "SUCCEEDED":
                    transcription_url = result.get("transcription_url")
                    if transcription_url:
                        raw_result = self._download_transcription_result(transcription_url)
                        return raw_result

            for result in results:
                if result.get("subtask_status") == "FAILED":
                    if self._is_no_words_response(result):
                        return {"transcripts": []}
                    message = result.get("message", result)
                    if self._is_instance_pool_exhausted(message) and exhausted_retries < 5:
                        exhausted_retries += 1
                        time.sleep(max(self.config.poll_interval_sec, 10.0))
                        break
                    raise ProviderExecutionError(f"Aliyun transcription subtask failed: {message}")
            else:
                time.sleep(self.config.poll_interval_sec)
                continue
            continue


class AliyunTranscriber:
    provider_name = "aliyun"
    chunk_duration_seconds = 1800
    chunk_max_workers = 4

    def __init__(
        self,
        config: AliyunTranscriberConfig,
        *,
        artifact_store: ArtifactStore | None = None,
        asr_client: AliyunAsrClient | None = None,
    ):
        self.config = config
        self.artifact_store = artifact_store or (AliyunOssStore(config.oss) if AliyunOssStore else None)
        self.asr_client = asr_client or AliyunAsrClient(config.asr)

    def _build_object_key(self, audio_path: Path) -> str:
        prefix = self.config.oss.object_prefix.strip("/")
        unique_id = uuid4().hex
        if prefix:
            return f"{prefix}/{unique_id}/{audio_path.name}"
        return f"{unique_id}/{audio_path.name}"

    def _prepare_audio_for_transcription(self, audio_path: Path, *, output_dir: Path | None = None) -> Path:
        return prepare_audio_for_transcription(audio_path, output_dir=output_dir)

    def _split_audio_for_transcription(self, normalized_audio_path: Path) -> list[tuple[Path, float]]:
        return split_audio_by_duration(
            normalized_audio_path,
            normalized_audio_path.parent / "transcription_chunks_aliyun",
            chunk_duration_seconds=self.chunk_duration_seconds,
        )

    def _transcribe_chunk_from_url(self, file_url: str) -> list[TranscriptSegment]:
        return parse_aliyun_transcription_result(self._transcribe_chunk_raw_from_url(file_url))

    def _transcribe_chunk_raw_from_url(self, file_url: str) -> dict[str, Any]:
        return self.asr_client.transcribe_raw_from_url(file_url)

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        normalized_audio_path = self._prepare_audio_for_transcription(request.audio_path, output_dir=request.work_dir)
        chunks = self._split_audio_for_transcription(normalized_audio_path)
        chunks_dir = chunks[0][0].parent if chunks else None
        total_chunks = len(chunks)

        def transcribe_one(index: int, chunk_path: Path, offset_seconds: float) -> tuple[list[TranscriptSegment], dict[str, Any]]:
            started = time.perf_counter()
            log_transcription_event(
                "transcription_chunk_started",
                provider=self.provider_name,
                chunk_index=index,
                chunk_count=total_chunks,
                chunk_name=chunk_path.name,
                offset_seconds=offset_seconds,
            )
            if self.artifact_store is None:
                raise ProviderExecutionError("Artifact store is not configured for Aliyun transcription.")
            object_key = self._build_object_key(chunk_path)
            self.artifact_store.upload_file(chunk_path, object_key)
            try:
                signed_url = self.artifact_store.get_signed_download_url(object_key)
                raw_result = self._transcribe_chunk_raw_from_url(signed_url)
                chunk_segments = parse_aliyun_transcription_result(raw_result)
                merged = [
                    TranscriptSegment(
                        start=segment.start + offset_seconds,
                        end=segment.end + offset_seconds,
                        text=segment.text,
                        speaker=segment.speaker,
                        confidence=segment.confidence,
                    )
                    for segment in chunk_segments
                    if str(segment.text).strip()
                ]
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                log_transcription_event(
                    "transcription_chunk_completed",
                    provider=self.provider_name,
                    chunk_index=index,
                    chunk_count=total_chunks,
                    chunk_name=chunk_path.name,
                    elapsed_ms=elapsed_ms,
                    elapsed=format_elapsed_minutes_seconds(elapsed_ms),
                    segment_count=len(merged),
                )
                return (
                    merged,
                    {
                        "chunk_index": index,
                        "chunk_name": chunk_path.name,
                        "offset_seconds": offset_seconds,
                        "raw_result": raw_result,
                    },
                )
            finally:
                if self.artifact_store is not None and not self.config.oss.retain_remote_artifacts:
                    try:
                        self.artifact_store.delete_object(object_key)
                    except Exception:
                        pass

        chunk_results: dict[int, tuple[list[TranscriptSegment], dict[str, Any]]] = {}
        try:
            if len(chunks) > 1 and self.chunk_max_workers > 1:
                with ThreadPoolExecutor(max_workers=self.chunk_max_workers) as executor:
                    futures = {
                        executor.submit(transcribe_one, index, chunk_path, offset_seconds): index
                        for index, (chunk_path, offset_seconds) in enumerate(chunks, start=1)
                    }
                    for future in as_completed(futures):
                        index = futures[future]
                        chunk_results[index] = future.result()
            else:
                for index, (chunk_path, offset_seconds) in enumerate(chunks, start=1):
                    chunk_results[index] = transcribe_one(index, chunk_path, offset_seconds)
        finally:
            if chunks_dir is not None:
                shutil.rmtree(chunks_dir, ignore_errors=True)

        segments: list[TranscriptSegment] = []
        raw_chunks: list[dict[str, Any]] = []
        for index in sorted(chunk_results):
            chunk_segments, raw_chunk = chunk_results[index]
            segments.extend(chunk_segments)
            raw_chunks.append(raw_chunk)
        return TranscriptionResult(
            provider=self.provider_name,
            segments=segments,
            raw_response={
                "provider": self.provider_name,
                "chunks": raw_chunks,
            },
        )
