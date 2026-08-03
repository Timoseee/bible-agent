import logging
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QComboBox, QVBoxLayout, QWidget)

from modules.config_loader import load_config
from frontend.components.file_selector import FileSelector
from frontend.components.log_panel import LogPanel
from frontend.components.progress_panel import ProgressPanel
from frontend.workers.pipeline_worker import PipelineWorker


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BibleAI Settings")
        config = load_config()
        form = QFormLayout(self)
        self.provider = QComboBox()
        self.provider.addItems(["DeepSeek", "OpenAI"])
        self.provider.setCurrentText("OpenAI" if config["ai_provider"] == "openai" else "DeepSeek")
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Leave blank to keep the existing key")
        status = "Configured" if config["deepseek_api_key_configured"] or config["openai_api_key_configured"] else "Missing"
        self.status = QLabel(status)
        form.addRow("API provider", self.provider)
        form.addRow("API key", self.api_key)
        form.addRow("Key status", self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def save(self):
        root = Path(__file__).resolve().parent.parent
        env_path = root / ".env"
        values = {"AI_PROVIDER": self.provider.currentText().lower(), "VISION_PROVIDER": self.provider.currentText().lower()}
        if self.api_key.text().strip():
            key_name = "OPENAI_API_KEY" if values["AI_PROVIDER"] == "openai" else "DEEPSEEK_API_KEY"
            values[key_name] = self.api_key.text().strip()
        existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
        lines = existing.splitlines()
        for key, value in values.items():
            replaced = False
            for index, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[index] = f"{key}={value}"; replaced = True; break
            if not replaced:
                lines.append(f"{key}={value}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, worker_factory=PipelineWorker):
        super().__init__()
        self.worker_factory = worker_factory
        self.thread = None
        self.worker = None
        self.output_path = ""
        self.setWindowTitle("BibleAI - Sermon Processing Assistant")
        self.resize(900, 760)
        self._build_menu()
        root = QWidget(); self.setCentralWidget(root)
        layout = QVBoxLayout(root); layout.setContentsMargins(28, 24, 28, 24); layout.setSpacing(16)
        header = QHBoxLayout()
        brand = QLabel("BibleAI"); brand.setObjectName("brand")
        subtitle = QLabel("Sermon Processing Assistant"); subtitle.setObjectName("muted")
        header.addWidget(brand); header.addWidget(subtitle); header.addStretch()
        settings = QPushButton("Settings"); settings.clicked.connect(self.show_settings); header.addWidget(settings)
        layout.addLayout(header)
        self.selector = FileSelector(); layout.addWidget(self.selector)
        self.progress_panel = ProgressPanel(); layout.addWidget(self.progress_panel)
        self.start_button = QPushButton("Start Processing"); self.start_button.setObjectName("primaryButton")
        self.start_button.setMinimumHeight(42); self.start_button.clicked.connect(self.start_processing); layout.addWidget(self.start_button)
        self.log_panel = LogPanel(); layout.addWidget(self.log_panel)
        output_row = QHBoxLayout(); output_row.addWidget(QLabel("Output")); output_row.addStretch()
        self.open_file_button = QPushButton("Open File"); self.open_file_button.setEnabled(False); self.open_file_button.clicked.connect(self.open_file)
        self.open_folder_button = QPushButton("Open Output Folder"); self.open_folder_button.clicked.connect(self.open_folder)
        output_row.addWidget(self.open_file_button); output_row.addWidget(self.open_folder_button); layout.addLayout(output_row)
        self.output_label = QLabel("No output generated yet."); self.output_label.setObjectName("muted"); layout.addWidget(self.output_label)
        self.statusBar().showMessage("Ready")
        self.setAcceptDrops(True)

    def _build_menu(self):
        settings_action = QAction("Settings", self); settings_action.triggered.connect(self.show_settings)
        self.menuBar().addAction(settings_action)

    def show_settings(self):
        SettingsDialog(self).exec()

    def start_processing(self):
        if not self.selector.path or self.selector.input_type not in {"audio", "image", "image_folder"}:
            QMessageBox.warning(self, "Input required", "Select an audio file or image folder first."); return
        if self.thread and self.thread.isRunning(): return
        self.start_button.setEnabled(False); self.open_file_button.setEnabled(False)
        self.progress_panel.update_status(0, "Starting…"); self.log_panel.append_log("Preparing pipeline.")
        self.thread = QThread(self)
        self.worker = self.worker_factory(self.selector.path)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress_panel.update_status)
        self.worker.log.connect(self.log_panel.append_log)
        self.worker.finished.connect(self.processing_finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def processing_finished(self, result):
        self.start_button.setEnabled(True)
        if result.get("success"):
            self.output_path = result.get("output", "")
            self.open_file_button.setEnabled(bool(self.output_path and Path(self.output_path).exists()))
            self.output_label.setText(f"Output: {self.output_path}")
            self.statusBar().showMessage(f"Completed successfully: {self.output_path}")
        else:
            self.output_label.setText("No output generated.")
            self.statusBar().showMessage("Processing failed")
            QMessageBox.critical(self, "Processing failed", PipelineWorker.user_error(result))

    def open_file(self):
        if self.output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_path))

    def open_folder(self):
        folder = Path(self.output_path).parent if self.output_path else Path(__file__).resolve().parent.parent / "output" / "docx"
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            self.thread.quit(); self.thread.wait(3000)
        event.accept()
