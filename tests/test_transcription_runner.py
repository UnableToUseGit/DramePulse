from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

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
    def test_transcribe_video_to_srt_writes_result(self) -> None:
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
            output_path = tmp_path / "demo.srt"
            video_path.write_bytes(b"fake-video")

            transcriber = FakeTranscriber()
            result_path = transcribe_video_to_srt(
                video_path=video_path,
                output_path=output_path,
                transcriber=transcriber,
                language_hints=["zh"],
            )

            self.assertEqual(result_path, output_path)
            self.assertEqual(transcriber.requests[0].audio_path, video_path)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "1\n00:00:00,000 --> 00:00:01,000\n你好\n")
            raw_output_path = tmp_path / "demo.transcription.json"
            raw_payload = json.loads(raw_output_path.read_text(encoding="utf-8"))
            self.assertEqual(raw_payload["provider"], "fake_aliyun")
            self.assertEqual(raw_payload["raw_response"]["chunks"][0]["raw_result"]["transcripts"][0]["sentences"][0]["text"], "你好")


class AliyunTranscriberCleanupTest(unittest.TestCase):
    def test_transcriber_removes_local_chunks_and_keeps_normalized_audio(self) -> None:
        class FakeArtifactStore:
            def upload_file(self, local_path: Path, object_key: str) -> str:
                return object_key

            def get_signed_download_url(self, object_key: str, expires: int | None = None) -> str:
                return f"https://example.com/{object_key}"

            def delete_object(self, object_key: str) -> None:
                return None

        class FakeAliyunTranscriber(AliyunTranscriber):
            def _prepare_audio_for_transcription(self, audio_path: Path) -> Path:
                normalized = audio_path.parent / f"{audio_path.stem}.16k-mono.wav"
                normalized.write_bytes(b"normalized-audio")
                return normalized

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
            transcriber = FakeAliyunTranscriber(
                config=__import__("scripts.transcription.config", fromlist=["AliyunTranscriberConfig"]).AliyunTranscriberConfig(),
                artifact_store=FakeArtifactStore(),
            )

            result = transcriber.transcribe(TranscriptionRequest(audio_path=video_path))

            self.assertTrue((tmp_path / "demo.16k-mono.wav").exists())
            self.assertFalse((tmp_path / "transcription_chunks_aliyun").exists())
            self.assertEqual(result.segments[0].text, "你好")
            self.assertEqual(result.raw_response["chunks"][0]["raw_result"]["transcripts"][0]["sentences"][0]["text"], "你好")


if __name__ == "__main__":
    unittest.main()
