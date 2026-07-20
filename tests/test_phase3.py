"""Phase 3 tests for raw audio transcription setup."""

import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.audio_transcriber import AudioTranscriptionError, transcribe_audio
from modules.config_loader import load_config


TEST_WORK_DIR = Path(__file__).resolve().parent / "tmp_phase3"


class Phase3AudioTranscriptionTests(unittest.TestCase):
    def setUp(self):
        TEST_WORK_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if TEST_WORK_DIR.exists():
            shutil.rmtree(TEST_WORK_DIR)

    def test_api_configuration_detection(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            config = load_config()
        self.assertTrue(config["openai_api_key_configured"])
        self.assertEqual(config["openai_api_key"], "test-key")

    def test_missing_file_handling(self):
        missing_path = TEST_WORK_DIR / "missing.mp3"
        with self.assertRaises(FileNotFoundError):
            transcribe_audio(missing_path)

    def test_invalid_extension_handling(self):
        text_path = TEST_WORK_DIR / "notes.txt"
        text_path.write_text("not audio", encoding="utf-8")
        with self.assertRaises(AudioTranscriptionError):
            transcribe_audio(text_path)

    def test_audio_path_validation_without_api_key(self):
        audio_path = TEST_WORK_DIR / "sermon.m4a"
        audio_path.touch()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            with self.assertRaises(AudioTranscriptionError) as context:
                transcribe_audio(audio_path)
        self.assertIn("OPENAI_API_KEY", str(context.exception))


if __name__ == "__main__":
    unittest.main()
