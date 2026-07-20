"""Image metadata analysis for ordering and chapter detection preparation."""

import json
import re
from pathlib import Path

from modules.image_ocr import SUPPORTED_IMAGE_EXTENSIONS


PAGE_PATTERNS = [
    re.compile(r"(?:第\s*)?(\d+)\s*页"),
    re.compile(r"\b(\d+)\s*/\s*\d+\b"),
]
CHAPTER_PATTERNS = [
    re.compile(r"([\u4e00-\u9fff]{2,10}(?:记|书|福音|行传))\s*(\d+)\s*(?:章|篇)?"),
    re.compile(r"\b(\d+)\s*:\s*\d+\b"),
]


def _empty_metadata(image_path, confidence=0.0):
    return {
        "filename": Path(image_path).name,
        "page_number": None,
        "chapter_reference": "",
        "first_text": "",
        "last_text": "",
        "confidence": confidence,
    }


def _parse_metadata_from_text(image_path, text):
    metadata = _empty_metadata(image_path, confidence=0.35 if text else 0.0)
    normalized_text = text.strip()

    for pattern in PAGE_PATTERNS:
        match = pattern.search(normalized_text)
        if match:
            metadata["page_number"] = int(match.group(1))
            metadata["confidence"] = max(metadata["confidence"], 0.95)
            break

    for pattern in CHAPTER_PATTERNS:
        match = pattern.search(normalized_text)
        if match:
            metadata["chapter_reference"] = match.group(0)
            metadata["confidence"] = max(metadata["confidence"], 0.75)
            break

    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
    if lines:
        metadata["first_text"] = lines[0][:120]
        metadata["last_text"] = lines[-1][-120:]

    return metadata


def _normalize_provider_metadata(image_path, metadata):
    normalized = _empty_metadata(image_path)
    normalized.update({key: metadata.get(key, normalized[key]) for key in normalized})

    if normalized["page_number"] is not None:
        normalized["page_number"] = int(normalized["page_number"])

    normalized["confidence"] = float(normalized.get("confidence") or 0.0)
    return normalized


def analyze_image(image_path, provider=None):
    """Analyze one image and extract ordering metadata."""
    path = Path(image_path)

    if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        metadata = _empty_metadata(path)
        metadata["error"] = "Unsupported image format."
        return metadata

    if provider is not None and hasattr(provider, "analyze_image"):
        return _normalize_provider_metadata(path, provider.analyze_image(path))

    if provider is not None and hasattr(provider, "generate_from_image"):
        response = provider.generate_from_image(
            "Analyze this image for page number, chapter reference, first text, and last text.",
            path,
        )
        try:
            return _normalize_provider_metadata(path, json.loads(response))
        except json.JSONDecodeError:
            return _parse_metadata_from_text(path, response)

    return _empty_metadata(path)
