"""OCR text cleaning pipeline."""

import re

from opencc import OpenCC

from modules.watermark_detector import (
    clean_watermarks,
    detect_watermarks,
    load_watermark_database,
)


IMAGE_EXPORT_ARTIFACT_PATTERN = re.compile(
    r"^\s*(?:第[一二三四五六七八九十百千万零〇两0-9]+\s*(?:页|章)|来自\s*小米笔记)\s*$"
)
SIMPLIFIED_CHINESE = OpenCC("t2s")


def to_simplified_chinese(text):
    """Normalize Chinese script without guessing transcription corrections."""
    return SIMPLIFIED_CHINESE.convert(str(text or ""))


def clean_image_ocr_text(text):
    """Remove only known image-export labels while preserving all other layout."""
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    kept_lines = []
    removed_artifacts = []
    for line in value.split("\n"):
        if IMAGE_EXPORT_ARTIFACT_PATTERN.fullmatch(line):
            removed_artifacts.append(line.strip())
        else:
            kept_lines.append(line)
    return {
        "cleaned_text": "\n".join(kept_lines).strip("\n"),
        "removed_watermarks": removed_artifacts,
    }


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
    characters, converts Traditional Chinese to Simplified Chinese,
    normalizes line endings, trims trailing whitespace, and limits excessive
    blank lines. Bible terminology and wording changes are
    handled later by the correction and review stages.
    """
    value = to_simplified_chinese(text).replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    lines = [line.rstrip() for line in value.split("\n")]
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return {
        "cleaned_text": cleaned,
        "changed": cleaned != str(text or ""),
    }
