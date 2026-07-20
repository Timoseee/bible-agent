"""Watermark detection and safe text cleaning helpers."""

import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_WATERMARK_DATABASE_PATH = BASE_DIR / "database" / "watermarks.json"


def load_watermark_database(database_path=DEFAULT_WATERMARK_DATABASE_PATH):
    """Load watermark definitions from JSON."""
    path = Path(database_path)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def detect_watermarks(text, database=None):
    """Detect known watermark text without modifying content."""
    if not text:
        return {"found": False, "watermarks": []}

    database = database or load_watermark_database()
    watermarks = []

    matched_known = []
    for watermark in sorted(database.get("common_watermarks", []), key=len, reverse=True):
        if watermark and watermark in text:
            if any(watermark in existing for existing in matched_known):
                continue

            matched_known.append(watermark)
            watermarks.append(
                {
                    "text": watermark,
                    "type": "known_watermark",
                    "position": None,
                }
            )

    for pattern in database.get("patterns", []):
        if pattern and re.search(pattern, text):
            watermarks.append(
                {
                    "text": pattern,
                    "type": "pattern_watermark",
                    "position": None,
                }
            )

    return {
        "found": bool(watermarks),
        "watermarks": watermarks,
    }


def clean_watermarks(text, detected_watermarks):
    """Remove only confirmed watermark strings while preserving other text."""
    cleaned_text = text

    for watermark in detected_watermarks:
        if watermark.get("type") != "known_watermark":
            continue

        watermark_text = watermark.get("text", "")
        if watermark_text:
            cleaned_text = cleaned_text.replace(watermark_text, "")

    cleaned_text = re.sub(r"[ \t]+\n", "\n", cleaned_text)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
    return cleaned_text.strip()
