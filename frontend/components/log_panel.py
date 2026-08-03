from datetime import datetime

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QFrame, QLabel, QTextEdit, QVBoxLayout


class LogPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        title = QLabel("Activity log")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.viewer = QTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setMinimumHeight(150)
        layout.addWidget(self.viewer)

    def append_log(self, message: str, level: str = "INFO"):
        stamp = datetime.now().strftime("%H:%M")
        cursor = self.viewer.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(f"[{stamp}] {level}: {message}\n")
        self.viewer.setTextCursor(cursor)
