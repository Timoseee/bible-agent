"""OCR text cleaning pipeline."""

from modules.watermark_detector import (
    clean_watermarks,
    detect_watermarks,
    load_watermark_database,
)


def clean_ocr_text(text):
    """Detect and remove confirmed watermark text from OCR output."""
    database = load_watermark_database()
    detection = detect_watermarks(text, database)
    cleaned_text = clean_watermarks(text, detection["watermarks"])

    return {
        "cleaned_text": cleaned_text,
        "removed_watermarks": detection["watermarks"],
    }
