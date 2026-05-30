from __future__ import annotations

import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from scripts import generate_audio_visualization


class AudioVisualizationScriptTest(unittest.TestCase):
    def test_resolve_media_input_derives_media_id_from_stem(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            media_path = Path(tmpdir) / "video.mp4"
            media_path.write_bytes(b"fake")

            media = generate_audio_visualization.resolve_media_input(media_path)

            self.assertEqual(media.media_id, "video")
            self.assertEqual(media.media_path, media_path.resolve())

    def test_generate_visualization_writes_energy_json_and_waveform_svg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            media_path = tmp_path / "video.mp4"
            media_path.write_bytes(b"fake")

            def fake_extract_energy(media_path: Path, sample_interval: float):
                self.assertEqual(sample_interval, 0.1)
                return [
                    generate_audio_visualization.EnergySample(time=0.0, rms_db=-40.0),
                    generate_audio_visualization.EnergySample(time=0.1, rms_db=-20.0),
                    generate_audio_visualization.EnergySample(time=0.2, rms_db=-60.0),
                ]

            def fake_write_spectrogram(media_path: Path, output_path: Path) -> None:
                output_path.write_bytes(b"png")

            result = generate_audio_visualization.generate_visualization(
                generate_audio_visualization.MediaInput(
                    media_id="demo_ep01",
                    media_path=media_path.resolve(),
                ),
                output_root=tmp_path / "output",
                sample_interval=0.1,
                extract_energy=fake_extract_energy,
                write_spectrogram=fake_write_spectrogram,
            )

            self.assertEqual(result.output_dir, tmp_path / "output" / "demo_ep01" / "audio")
            self.assertTrue(result.energy_json_path.is_file())
            self.assertTrue(result.waveform_svg_path.is_file())
            self.assertTrue(result.spectrogram_png_path.is_file())

            payload = json.loads(result.energy_json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["media_id"], "demo_ep01")
            self.assertEqual(payload["sample_interval"], 0.1)
            self.assertEqual(payload["samples"][1]["rms_db"], -20.0)
            self.assertEqual(payload["summary"]["peak_rms_db"], -20.0)
            self.assertEqual(payload["summary"]["duration"], 0.2)
            svg = result.waveform_svg_path.read_text(encoding="utf-8")
            self.assertIn("<svg", svg)
            self.assertIn("DramePulse Audio Energy", svg)

    def test_extract_energy_calculates_rms_windows_from_pcm(self) -> None:
        class FakeCompletedProcess:
            stdout = (
                struct.pack("<10h", *([1000] * 10))
                + struct.pack("<10h", *([0] * 10))
                + struct.pack("<10h", *([2000] * 10))
            )

        with patch("scripts.generate_audio_visualization.subprocess.run", return_value=FakeCompletedProcess()):
            samples = generate_audio_visualization.extract_energy_samples(
                Path("video.mp4"),
                sample_interval=0.1,
                sample_rate=100,
            )

        self.assertEqual(len(samples), 3)
        self.assertAlmostEqual(samples[0].rms_db, -30.309, places=3)
        self.assertEqual(samples[1], generate_audio_visualization.EnergySample(time=0.1, rms_db=-100.0))
        self.assertAlmostEqual(samples[2].rms_db, -24.288, places=3)


if __name__ == "__main__":
    unittest.main()
