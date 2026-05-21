from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
