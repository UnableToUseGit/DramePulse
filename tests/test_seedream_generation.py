from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pipelines.highlight_commerce.seedream_generation import (
    SeedreamImageGenerationClient,
    SeedreamImageRequest,
    download_generated_image,
)


class _FakeImages:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> object:
        self.calls.append(kwargs)

        class _Image:
            url = "https://example.test/cartoon-avatar.png"
            b64_json = None

        class _Response:
            data = [_Image()]

        return _Response()


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.images = _FakeImages()


class SeedreamImageGenerationClientTest(unittest.TestCase):
    def test_generate_image_sends_prompt_and_reference_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            character_image = root / "character.png"
            style_image = root / "style.webp"
            character_image.write_bytes(b"character")
            style_image.write_bytes(b"style")
            fake_client = _FakeOpenAIClient()
            client = SeedreamImageGenerationClient(
                api_key="test-key",
                base_url="https://ark.example.test/api/v3",
                model_name="seedream-test",
                openai_client=fake_client,
            )

            result = client.generate_image(
                SeedreamImageRequest(
                    prompt="生成卡通角色",
                    reference_image_paths=[character_image, style_image],
                    size="2K",
                    output_format="png",
                    response_format="url",
                    watermark=False,
                )
            )

        self.assertEqual(result.url, "https://example.test/cartoon-avatar.png")
        self.assertEqual(len(fake_client.images.calls), 1)
        call = fake_client.images.calls[0]
        self.assertEqual(call["model"], "seedream-test")
        self.assertEqual(call["prompt"], "生成卡通角色")
        self.assertEqual(call["size"], "2K")
        self.assertEqual(call["output_format"], "png")
        self.assertEqual(call["response_format"], "url")
        self.assertEqual(call["extra_body"]["watermark"], False)  # type: ignore[index]
        self.assertEqual(call["extra_body"]["sequential_image_generation"], "disabled")  # type: ignore[index]
        images = call["extra_body"]["image"]  # type: ignore[index]
        self.assertEqual(len(images), 2)
        self.assertTrue(images[0].startswith("data:image/png;base64,"))
        self.assertTrue(images[1].startswith("data:image/webp;base64,"))

    def test_download_generated_image_writes_response_body(self) -> None:
        class FakeHttpClient:
            def get(self, url: str, timeout: int) -> object:
                self.url = url
                self.timeout = timeout

                class Response:
                    content = b"avatar-bytes"

                    def raise_for_status(self) -> None:
                        return None

                return Response()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "cartoon_avatar.png"
            http_client = FakeHttpClient()

            downloaded_path = download_generated_image(
                "https://example.test/avatar.png",
                output_path,
                http_client=http_client,
            )
            output_bytes = output_path.read_bytes()

        self.assertEqual(downloaded_path, output_path)
        self.assertEqual(output_bytes, b"avatar-bytes")
        self.assertEqual(http_client.url, "https://example.test/avatar.png")


if __name__ == "__main__":
    unittest.main()
