from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class FileSelector(QFrame):
    """Input picker with a drop target and automatic type summary."""

    pathChanged = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        self.path = ""
        self.input_type = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel("Input files")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        buttons = QHBoxLayout()
        self.audio_button = QPushButton("Select Audio")
        self.folder_button = QPushButton("Select Image Folder")
        buttons.addWidget(self.audio_button)
        buttons.addWidget(self.folder_button)
        layout.addLayout(buttons)
        self.drop_label = QLabel("Drop an audio file or image folder here")
        self.drop_label.setObjectName("dropHint")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setMinimumHeight(62)
        layout.addWidget(self.drop_label)
        self.detected_label = QLabel("Detected type: —")
        self.detected_label.setObjectName("muted")
        layout.addWidget(self.detected_label)
        self.audio_button.clicked.connect(self.select_audio)
        self.folder_button.clicked.connect(self.select_folder)

    def set_path(self, path: str, input_type: str = ""):
        self.path = str(path)
        self.input_type = input_type or self.detect_type(self.path)
        self.drop_label.setText(Path(self.path).name or self.path)
        label = {"audio": "Audio", "image": "Image", "image_folder": "Image folder"}.get(self.input_type, "Unsupported")
        self.detected_label.setText(f"Detected type: {label}")
        self.pathChanged.emit(self.path, self.input_type)

    @staticmethod
    def detect_type(path: str) -> str:
        candidate = Path(path)
        if candidate.is_dir():
            return "image_folder"
        if candidate.suffix.lower() in {".mp3", ".m4a"}:
            return "audio"
        if candidate.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            return "image"
        return "unsupported"

    def select_audio(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Select audio", "", "Audio (*.mp3 *.m4a)")
        if path:
            self.set_path(path, "audio")

    def select_folder(self):
        from PySide6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "Select image folder")
        if path:
            self.set_path(path, "image_folder")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            input_type = self.detect_type(path)
            if input_type in {"audio", "image", "image_folder"}:
                self.set_path(path, input_type)
                event.acceptProposedAction()
