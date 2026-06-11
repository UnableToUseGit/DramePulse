from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pipelines.highlight_commerce.seedance_generation import (
    SeedanceClient,
    SeedanceTaskResult,
    _asset_audio_url,
    _asset_image_url,
    _parse_seedance_task_response,
    attach_seedance_render,
)


class SeedanceGenerationTest(unittest.TestCase):
    def test_parse_seedance_response_reads_video_url_from_content_object(self) -> None:
        class Content:
            video_url = "https://example.test/content-object.mp4"

        class Response:
            id = "task-content-object"
            status = "succeeded"
            content = Content()

        result = _parse_seedance_task_response(Response())

        self.assertEqual(result.task_id, "task-content-object")
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.video_url, "https://example.test/content-object.mp4")

    def test_parse_seedance_response_reads_video_url_from_dict_content(self) -> None:
        result = _parse_seedance_task_response(
            {
                "task_id": "task-dict",
                "status": "succeeded",
                "content": {"video_url": "https://example.test/dict.mp4"},
            }
        )

        self.assertEqual(result.task_id, "task-dict")
        self.assertEqual(result.video_url, "https://example.test/dict.mp4")

    def test_asset_image_url_converts_local_image_to_data_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "image.png"
            image_path.write_bytes(b"png-bytes")

            url = _asset_image_url(image_path)

        self.assertEqual(url, "data:image/png;base64,cG5nLWJ5dGVz")

    def test_asset_image_url_keeps_remote_url(self) -> None:
        self.assertEqual(
            _asset_image_url("https://example.test/image.png"),
            "https://example.test/image.png",
        )

    def test_asset_audio_url_converts_local_mp3_to_data_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "voice.mp3"
            audio_path.write_bytes(b"voice-bytes")

            url = _asset_audio_url(audio_path)

        self.assertEqual(url, "data:audio/mpeg;base64,dm9pY2UtYnl0ZXM=")

    def test_seedance_client_create_and_get_task_parse_sdk_responses(self) -> None:
        class FakeTasks:
            def __init__(self) -> None:
                self.create_kwargs: dict[str, object] | None = None
                self.get_kwargs: dict[str, object] | None = None

            def create(self, **kwargs: object) -> object:
                self.create_kwargs = kwargs
                return {"id": "task-created", "status": "queued"}

            def get(self, **kwargs: object) -> object:
                self.get_kwargs = kwargs
                return {
                    "id": "task-created",
                    "status": "succeeded",
                    "content": {"video_url": "https://example.test/output.mp4"},
                }

        class FakeContentGeneration:
            def __init__(self) -> None:
                self.tasks = FakeTasks()

        class FakeArk:
            def __init__(self) -> None:
                self.content_generation = FakeContentGeneration()

        ark = FakeArk()
        client = SeedanceClient(ark_client=ark)

        created = client.create_task(
            model="doubao-seedance-2-0-260128",
            content=[{"type": "text", "text": "prompt"}],
            generate_audio=True,
            ratio="9:16",
            duration=12,
            watermark=False,
        )
        fetched = client.get_task("task-created")

        self.assertEqual(created, SeedanceTaskResult(task_id="task-created", status="queued"))
        self.assertEqual(fetched.video_url, "https://example.test/output.mp4")
        self.assertEqual(ark.content_generation.tasks.create_kwargs["duration"], 12)
        self.assertEqual(ark.content_generation.tasks.get_kwargs, {"task_id": "task-created"})

    def test_attach_seedance_render_preserves_asset_fields(self) -> None:
        updated = attach_seedance_render(
            {"asset_id": "asset-001", "render": {"previous": True}},
            SeedanceTaskResult(
                task_id="task-002",
                status="succeeded",
                video_url="https://example.test/output.mp4",
            ),
        )

        self.assertEqual(updated["asset_id"], "asset-001")
        self.assertEqual(updated["render"]["previous"], True)
        self.assertEqual(updated["render"]["provider_job_id"], "task-002")
        self.assertEqual(updated["render"]["output_video_url"], "https://example.test/output.mp4")


if __name__ == "__main__":
    unittest.main()
