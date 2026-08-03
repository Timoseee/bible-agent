import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

try:
    from PySide6.QtWidgets import QApplication
    from frontend.components.file_selector import FileSelector
    from frontend.main_window import MainWindow
    from frontend.workers.pipeline_worker import PipelineWorker
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_main_window_loads(self):
        window = MainWindow(); self.assertEqual(window.windowTitle(), "BibleAI - Sermon Processing Assistant"); window.close()

    def test_file_detection(self):
        self.assertEqual(FileSelector.detect_type("sermon.mp3"), "audio")
        self.assertEqual(FileSelector.detect_type("notes.png"), "image")
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(FileSelector.detect_type(folder), "image_folder")

    def test_worker_mock_processing(self):
        processor = Mock(return_value={"success": True, "output": "result.docx", "steps": ["DOCX generated"]})
        worker = PipelineWorker("sermon.mp3", processor)
        worker.run()
        processor.assert_called_once_with("sermon.mp3")


if __name__ == "__main__":
    unittest.main()
