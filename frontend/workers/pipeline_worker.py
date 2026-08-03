import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from modules.pipeline_controller import process_input


class PipelineWorker(QObject):
    progress = Signal(int, str)
    log = Signal(str, str)
    finished = Signal(dict)

    def __init__(self, input_path: str, processor=None):
        super().__init__()
        self.input_path = input_path
        self.processor = processor or process_input

    @Slot()
    def run(self):
        try:
            input_type = "image_folder" if Path(self.input_path).is_dir() else "audio"
            stages = (["Collecting images…", "Ordering images…", "Reading image text…"]
                      if input_type == "image_folder" else ["Transcribing audio…"])
            stages += ["Checking Bible terminology…", "Correcting text…", "Reviewing…", "Generating DOCX…"]
            self.log.emit("Processing started.", "INFO")
            for index, stage in enumerate(stages[:1], 1):
                self.progress.emit(5, stage)
                self.log.emit(stage, "INFO")
            result = self.processor(self.input_path)
            steps = result.get("steps", [])
            for index, step in enumerate(steps, 1):
                value = min(95, 10 + int(index * 80 / max(1, len(steps))))
                self.progress.emit(value, step)
                self.log.emit(step, "INFO")
            if result.get("success"):
                self.progress.emit(100, "Completed.")
                self.log.emit("Completed successfully.", "INFO")
            else:
                self.log.emit(self.user_error(result), "ERROR")
            self.finished.emit(result)
        except Exception as error:
            logging.exception("GUI pipeline worker failed")
            result = {"success": False, "input": self.input_path, "step": "unknown", "error": str(error)}
            self.log.emit("Processing failed. Check the configuration and input file.", "ERROR")
            self.finished.emit(result)

    @staticmethod
    def user_error(result: dict) -> str:
        step = str(result.get("step", "processing")).lower()
        if "transcrib" in step:
            return "Audio transcription failed. Please check API configuration."
        if "ocr" in step or "image" in step:
            return "Image reading failed. Please check the image folder and API configuration."
        if "docx" in step:
            return "DOCX generation failed. Please check the templates and output folder."
        return "Processing failed. Please check the input and API configuration."
