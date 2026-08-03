from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout


class ProgressPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        title = QLabel("Processing")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        layout.addWidget(self.progress)
        self.step_label = QLabel("Current step: Waiting…")
        self.step_label.setObjectName("muted")
        layout.addWidget(self.step_label)

    def update_status(self, value: int, step: str):
        self.progress.setValue(value)
        self.step_label.setText(f"Current step: {step}")
