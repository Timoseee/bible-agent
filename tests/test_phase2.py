"""Phase 2 examples for input classification and audio duration checks."""

import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.audio_processor import analyze_audio
from modules.input_classifier import classify_input


TEST_WORK_DIR = Path(__file__).resolve().parent / "tmp_phase2"


class FakeAudioInfo:
    def __init__(self, length):
        self.length = length


class FakeAudio:
    def __init__(self, length):
        self.info = FakeAudioInfo(length)


class Phase2InputProcessingTests(unittest.TestCase):
    def setUp(self):
        TEST_WORK_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if TEST_WORK_DIR.exists():
            shutil.rmtree(TEST_WORK_DIR)

    def test_mp3_detection(self):
        path = TEST_WORK_DIR / "sermon.mp3"
        path.touch()
        self.assertEqual(classify_input(path)["type"], "audio")
        self.assertEqual(classify_input(path)["extension"], ".mp3")

    def test_m4a_detection(self):
        path = TEST_WORK_DIR / "sermon.m4a"
        path.touch()
        self.assertEqual(classify_input(path)["type"], "audio")
        self.assertEqual(classify_input(path)["extension"], ".m4a")

    def test_image_detection(self):
        path = TEST_WORK_DIR / "page.png"
        path.touch()
        self.assertEqual(classify_input(path)["type"], "image")
        self.assertEqual(classify_input(path)["extension"], ".png")

    def test_image_folder_detection(self):
        folder = TEST_WORK_DIR / "pages"
        folder.mkdir()
        (folder / "page_1.jpg").touch()
        result = classify_input(folder)
        self.assertEqual(result["type"], "image_folder")
        self.assertEqual(result["image_count"], 1)

    def test_duration_within_limit(self):
        path = TEST_WORK_DIR / "sermon.mp3"
        path.touch()
        with patch("modules.audio_processor.File", return_value=FakeAudio(45 * 60)):
            result = analyze_audio(path)
        self.assertEqual(result["duration_minutes"], 45)
        self.assertTrue(result["within_limit"])

    def test_duration_over_limit(self):
        path = TEST_WORK_DIR / "long_sermon.mp3"
        path.touch()
        with patch("modules.audio_processor.File", return_value=FakeAudio(121 * 60)):
            result = analyze_audio(path)
        self.assertEqual(result["duration_minutes"], 121)
        self.assertFalse(result["within_limit"])
        self.assertEqual(result["warning"], "Audio is longer than the 2 hour limit.")


if __name__ == "__main__":
    unittest.main()
