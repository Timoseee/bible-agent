"""OCR text cleaning pipeline."""

import re

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


def clean_transcript_text(text):
    """Normalize Whisper output without rewriting sermon content.

    This stage is intentionally conservative: it removes transport/control
    characters, normalizes line endings, trims trailing whitespace, and
    limits excessive blank lines. Bible terminology and wording changes are
    handled later by the correction and review stages.
    """
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    lines = [line.rstrip() for line in value.split("\n")]
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return {
        "cleaned_text": cleaned,
        "changed": cleaned != str(text or ""),
    }
