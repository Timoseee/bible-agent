"""Tests for low-overhead automatic audio monitoring."""

import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from modules.audio_watcher import AudioFolderWatcher, WatcherSettings, process_in_worker


TEST_DIR = Path(__file__).resolve().parent / "tmp_audio_watcher"


class AudioFolderWatcherTests(unittest.TestCase):
    def setUp(self):
        TEST_DIR.mkdir(parents=True, exist_ok=True)
        self.input_dir = TEST_DIR / "input"
        self.input_dir.mkdir()
        self.settings = WatcherSettings(
            input_dir=self.input_dir,
            state_path=TEST_DIR / "state.json",
            stop_path=TEST_DIR / "stop.flag",
            scan_interval_seconds=0.01,
            stable_seconds=0,
            idle_seconds=0,
            retry_seconds=60,
            require_ac_power=False,
            notify_on_success=False,
        )

    def tearDown(self):
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)

    def test_processes_new_audio_only_once(self):
        audio_path = self.input_dir / "sermon.mp3"
        audio_path.write_bytes(b"audio")
        processor = Mock(return_value={"success": True, "output": "sermon.docx"})
        watcher = AudioFolderWatcher(self.settings, processor=processor)

        result = watcher.scan_once(now_monotonic=10, now_time=100)
        second_result = watcher.scan_once(now_monotonic=20, now_time=110)

        self.assertTrue(result["success"])
        self.assertIsNone(second_result)
        processor.assert_called_once_with(audio_path)

    def test_changed_file_is_processed_again(self):
        audio_path = self.input_dir / "sermon.mp3"
        audio_path.write_bytes(b"audio")
        processor = Mock(return_value={"success": True, "output": "sermon.docx"})
        watcher = AudioFolderWatcher(self.settings, processor=processor)
        watcher.scan_once(now_monotonic=10, now_time=100)

        audio_path.write_bytes(b"new audio content")
        result = watcher.scan_once(now_monotonic=20, now_time=110)

        self.assertTrue(result["success"])
        self.assertEqual(processor.call_count, 2)

    def test_failure_waits_before_retry(self):
        audio_path = self.input_dir / "sermon.m4a"
        audio_path.write_bytes(b"audio")
        processor = Mock(return_value={"success": False, "error": "network"})
        watcher = AudioFolderWatcher(self.settings, processor=processor)

        watcher.scan_once(now_monotonic=10, now_time=100)
        before_retry = watcher.scan_once(now_monotonic=20, now_time=130)
        after_retry = watcher.scan_once(now_monotonic=80, now_time=161)

        self.assertIsNone(before_retry)
        self.assertFalse(after_retry["success"])
        self.assertEqual(processor.call_count, 2)

    def test_mark_existing_creates_baseline(self):
        audio_path = self.input_dir / "existing.mp3"
        audio_path.write_bytes(b"audio")
        processor = Mock()
        watcher = AudioFolderWatcher(self.settings, processor=processor)

        self.assertEqual(watcher.mark_existing(), 1)
        self.assertIsNone(watcher.scan_once(now_monotonic=10, now_time=100))
        processor.assert_not_called()

    def test_worker_result_is_parsed(self):
        completed = SimpleNamespace(
            stdout='__BIBLEAI_WATCH_RESULT__={"success": true, "output": "done.docx"}\n',
            stderr="",
            returncode=0,
        )
        with patch("modules.audio_watcher.subprocess.run", return_value=completed):
            result = process_in_worker(self.input_dir / "sermon.mp3")

        self.assertTrue(result["success"])
        self.assertEqual(result["output"], "done.docx")


if __name__ == "__main__":
    unittest.main()
