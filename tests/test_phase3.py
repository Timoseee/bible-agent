"""Phase 3 tests for raw audio transcription setup."""

import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from openai import APIConnectionError, APITimeoutError, AuthenticationError

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
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "", "AUDIO_TRANSCRIPTION_PROVIDER": "openai"},
            clear=False,
        ):
            with self.assertRaises(AudioTranscriptionError) as context:
                transcribe_audio(audio_path)
        self.assertIn("OPENAI_API_KEY", str(context.exception))

    def test_local_transcription_does_not_require_openai_key(self):
        audio_path = TEST_WORK_DIR / "sermon.mp3"
        audio_path.touch()
        config = {
            "audio_transcription_provider": "local",
            "openai_api_key": "",
        }
        audio_info = {"duration_minutes": 1.0, "size_mb": 1.0, "warning": None}
        local_result = {
            "filename": "sermon.mp3",
            "language": "zh",
            "text": "本地转写文本",
            "provider": "local",
            "model": "small",
        }

        with patch("modules.audio_transcriber.load_config", return_value=config), patch(
            "modules.audio_transcriber.analyze_audio", return_value=audio_info
        ), patch(
            "modules.audio_transcriber._transcribe_local", return_value=local_result
        ) as local_transcribe:
            result = transcribe_audio(audio_path)

        self.assertEqual(result, local_result)
        local_transcribe.assert_called_once_with(audio_path, config)

    def _assert_transcription_api_error(self, api_error, expected_message):
        audio_path = TEST_WORK_DIR / "sermon.mp3"
        audio_path.touch()
        client = Mock()
        client.audio.transcriptions.create.side_effect = api_error
        config = {"openai_api_key": "test-key", "api_proxy": ""}
        audio_info = {"duration_minutes": 1.0, "size_mb": 1.0, "warning": None}

        with patch("modules.audio_transcriber.load_config", return_value=config), patch(
            "modules.audio_transcriber.analyze_audio", return_value=audio_info
        ), patch("modules.audio_transcriber.create_openai_client", return_value=client):
            with self.assertRaises(AudioTranscriptionError) as context:
                transcribe_audio(audio_path)

        self.assertIn(expected_message, str(context.exception))

    def test_connection_error_has_actionable_message(self):
        request = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")
        self._assert_transcription_api_error(
            APIConnectionError(request=request),
            "connection failed",
        )

    def test_timeout_error_has_actionable_message(self):
        request = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")
        self._assert_transcription_api_error(APITimeoutError(request), "timed out")

    def test_authentication_error_has_actionable_message(self):
        request = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")
        response = httpx.Response(401, request=request)
        self._assert_transcription_api_error(
            AuthenticationError("bad key", response=response, body=None),
            "authentication failed",
        )


if __name__ == "__main__":
    unittest.main()
