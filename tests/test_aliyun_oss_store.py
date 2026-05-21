from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.transcription.config import AliyunOssConfig
from scripts.transcription.errors import ProviderExecutionError
from scripts.transcription.storage.aliyun_oss import AliyunOssStore


class AliyunOssStoreTest(unittest.TestCase):
    def test_store_uploads_signs_and_deletes_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "demo.wav"
            local_path.write_bytes(b"audio")
            bucket = Mock()
            bucket.sign_url.return_value = "https://example.com/signed"

            with patch("scripts.transcription.storage.aliyun_oss.oss2") as oss2_mock:
                oss2_mock.Auth.return_value = "auth"
                oss2_mock.Bucket.return_value = bucket
                store = AliyunOssStore(
                    AliyunOssConfig(
                        endpoint="oss-cn-demo.aliyuncs.com",
                        bucket_name="demo-bucket",
                        access_key_id="access-key",
                        access_key_secret="access-secret",
                        signed_url_expires_sec=1800,
                    )
                )

            uploaded_key = store.upload_file(local_path, "audio/demo.wav")
            signed_url = store.get_signed_download_url("audio/demo.wav")
            store.delete_object("audio/demo.wav")

        self.assertEqual(uploaded_key, "audio/demo.wav")
        oss2_mock.Auth.assert_called_once_with("access-key", "access-secret")
        oss2_mock.Bucket.assert_called_once_with("auth", "oss-cn-demo.aliyuncs.com", "demo-bucket")
        bucket.put_object_from_file.assert_called_once_with("audio/demo.wav", str(local_path))
        bucket.sign_url.assert_called_once_with("GET", "audio/demo.wav", 1800)
        bucket.delete_object.assert_called_once_with("audio/demo.wav")
        self.assertEqual(signed_url, "https://example.com/signed")

    def test_store_requires_complete_oss_config(self) -> None:
        with self.assertRaisesRegex(ProviderExecutionError, "OSS config is incomplete"):
            AliyunOssStore(AliyunOssConfig(bucket_name="demo-bucket"))


if __name__ == "__main__":
    unittest.main()
