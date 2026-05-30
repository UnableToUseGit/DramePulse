from __future__ import annotations

import json
from pathlib import Path
import types
import tempfile
import unittest
from unittest.mock import patch

from scripts.transcription.config import AliyunAsrConfig
from scripts.transcription.providers.aliyun import AliyunAsrClient
from scripts.transcription.providers.aliyun import AliyunTranscriber
from scripts.transcription.runner import transcribe_video_to_srt
from scripts.transcription.srt import transcript_segments_to_srt
from scripts.transcription.types import TranscriptSegment, TranscriptionRequest, TranscriptionResult


class TranscriptSegmentsToSrtTest(unittest.TestCase):
    def test_transcript_segments_to_srt_formats_timestamps(self) -> None:
        srt = transcript_segments_to_srt(
            [
                TranscriptSegment(start=0.0, end=1.25, text="第一句"),
                TranscriptSegment(start=61.5, end=63.0, text="第二句"),
            ]
        )

        self.assertEqual(
            srt,
            "\n".join(
                [
                    "1",
                    "00:00:00,000 --> 00:00:01,250",
                    "第一句",
                    "",
                    "2",
                    "00:01:01,500 --> 00:01:03,000",
                    "第二句",
                    "",
                ]
            ),
        )


class TranscribeVideoToSrtTest(unittest.TestCase):
    def test_transcribe_video_to_srt_writes_outputs_to_directory(self) -> None:
        class FakeTranscriber:
            def __init__(self) -> None:
                self.requests: list[TranscriptionRequest] = []

            def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
                self.requests.append(request)
                return TranscriptionResult(
                    provider="fake_aliyun",
                    segments=[TranscriptSegment(start=0.0, end=1.0, text="你好")],
                    raw_response={
                        "chunks": [
                            {
                                "chunk_index": 1,
                                "offset_seconds": 0.0,
                                "raw_result": {"transcripts": [{"sentences": [{"text": "你好"}]}]},
                            }
                        ]
                    },
                )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "demo.mp4"
            output_dir = tmp_path / "output"
            video_path.write_bytes(b"fake-video")

            transcriber = FakeTranscriber()
            result_path = transcribe_video_to_srt(
                video_path=video_path,
                output_dir=output_dir,
                transcriber=transcriber,
                language_hints=["zh"],
            )

            self.assertEqual(result_path, output_dir / "demo.srt")
            self.assertEqual(transcriber.requests[0].audio_path, video_path)
            self.assertEqual(transcriber.requests[0].work_dir, output_dir)
            self.assertEqual(result_path.read_text(encoding="utf-8"), "1\n00:00:00,000 --> 00:00:01,000\n你好\n")
            raw_output_path = output_dir / "demo.transcription.json"
            raw_payload = json.loads(raw_output_path.read_text(encoding="utf-8"))
            self.assertEqual(raw_payload["provider"], "fake_aliyun")
            self.assertEqual(raw_payload["raw_response"]["chunks"][0]["raw_result"]["transcripts"][0]["sentences"][0]["text"], "你好")


class AliyunTranscriberCleanupTest(unittest.TestCase):
    def test_transcriber_uses_requested_work_dir_for_audio_artifacts(self) -> None:
        class FakeArtifactStore:
            def upload_file(self, local_path: Path, object_key: str) -> str:
                return object_key

            def get_signed_download_url(self, object_key: str, expires: int | None = None) -> str:
                return f"https://example.com/{object_key}"

            def delete_object(self, object_key: str) -> None:
                return None

        class FakeAliyunTranscriber(AliyunTranscriber):
            def _prepare_audio_for_transcription(self, audio_path: Path, *, output_dir: Path | None = None) -> Path:
                return super()._prepare_audio_for_transcription(audio_path, output_dir=output_dir)

            def _split_audio_for_transcription(self, normalized_audio_path: Path) -> list[tuple[Path, float]]:
                chunks_dir = normalized_audio_path.parent / "transcription_chunks_aliyun"
                chunks_dir.mkdir()
                chunk_path = chunks_dir / "chunk_000.wav"
                chunk_path.write_bytes(b"chunk")
                return [(chunk_path, 0.0)]

            def _transcribe_chunk_raw_from_url(self, file_url: str) -> dict[str, object]:
                return {
                    "transcripts": [
                        {
                            "sentences": [
                                {"begin_time": 0, "end_time": 1000, "text": "你好"},
                            ]
                        }
                    ]
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "demo.mp4"
            video_path.write_bytes(b"fake-video")
            output_dir = tmp_path / "outputs"
            transcriber = FakeAliyunTranscriber(
                config=__import__("scripts.transcription.config", fromlist=["AliyunTranscriberConfig"]).AliyunTranscriberConfig(),
                artifact_store=FakeArtifactStore(),
            )

            with patch("scripts.transcription.providers.aliyun.prepare_audio_for_transcription") as prepare_audio:
                prepare_audio.return_value = output_dir / "demo.16k-mono.wav"
                prepare_audio.return_value.parent.mkdir(parents=True)
                prepare_audio.return_value.write_bytes(b"normalized-audio")
                result = transcriber.transcribe(TranscriptionRequest(audio_path=video_path, work_dir=output_dir))

            prepare_audio.assert_called_once_with(video_path, output_dir=output_dir)
            self.assertTrue((output_dir / "demo.16k-mono.wav").exists())
            self.assertFalse((output_dir / "transcription_chunks_aliyun").exists())
            self.assertEqual(result.segments[0].text, "你好")
            self.assertEqual(result.raw_response["chunks"][0]["raw_result"]["transcripts"][0]["sentences"][0]["text"], "你好")


class AliyunAsrClientTest(unittest.TestCase):
    def test_transcribe_raw_from_url_returns_downloaded_result_without_parsing(self) -> None:
        class FakeTaskResponse:
            status_code = 200
            message = ""

            class output:
                task_id = "task_123"

        class FakeTranscriptionResponse:
            status_code = 200
            message = ""
            output = {
                "results": [
                    {
                        "subtask_status": "SUCCEEDED",
                        "transcription_url": "https://example.com/result.json",
                    }
                ]
            }

        class FakeTranscription:
            @staticmethod
            def async_call(**kwargs):
                return FakeTaskResponse()

            @staticmethod
            def wait(task: str):
                return FakeTranscriptionResponse()

        raw_result = {
            "transcripts": [
                {
                    "sentences": [
                        {"begin_time": 0, "end_time": 1000, "text": "你好"},
                    ]
                }
            ]
        }
        client = AliyunAsrClient(AliyunAsrConfig(api_key="demo"))
        dashscope_module = types.SimpleNamespace()
        audio_module = types.ModuleType("dashscope.audio")
        asr_module = types.ModuleType("dashscope.audio.asr")
        asr_module.Transcription = FakeTranscription

        with (
            patch.dict(
                "sys.modules",
                {
                    "dashscope": dashscope_module,
                    "dashscope.audio": audio_module,
                    "dashscope.audio.asr": asr_module,
                },
            ),
            patch.object(client, "_download_transcription_result", return_value=raw_result),
        ):
            result = client.transcribe_raw_from_url("https://example.com/audio.wav")

        self.assertEqual(result, raw_result)


if __name__ == "__main__":
    unittest.main()
