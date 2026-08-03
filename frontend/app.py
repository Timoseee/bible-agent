import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from frontend.main_window import MainWindow


def build_stylesheet():
    return """
    QWidget { background: #f6f8fb; color: #172033; font-size: 14px; }
    QMainWindow { background: #f6f8fb; }
    #brand { font-size: 29px; font-weight: 700; color: #244b8f; }
    #sectionTitle { font-size: 16px; font-weight: 650; }
    #muted, #dropHint { color: #65718a; }
    #card, #dropZone { background: white; border: 1px solid #dbe2ee; border-radius: 12px; }
    #dropZone { border: 1px dashed #9aacc9; }
    QPushButton { background: #edf2fa; border: 1px solid #d2dceb; border-radius: 7px; padding: 9px 16px; }
    QPushButton:hover { background: #dfe9f8; }
    #primaryButton { background: #2f66c2; color: white; border: 0; font-weight: 650; }
    #primaryButton:hover { background: #2455a7; }
    QProgressBar { min-height: 18px; border: 0; border-radius: 9px; background: #e5ebf4; text-align: center; }
    QProgressBar::chunk { border-radius: 9px; background: #4e82d7; }
    QTextEdit { border: 1px solid #dbe2ee; border-radius: 7px; background: #fbfcfe; }
    QLineEdit, QComboBox { padding: 7px; border: 1px solid #cfd8e8; border-radius: 6px; background: white; }
    """


def main():
    log_dir = ROOT / "logs"; log_dir.mkdir(exist_ok=True)
    logging.basicConfig(filename=log_dir / "gui_errors.log", level=logging.ERROR,
                        format="%(asctime)s %(levelname)s %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("BibleAI")
    app.setStyleSheet(build_stylesheet())
    window = MainWindow(); window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
