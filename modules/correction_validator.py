"""Automatic content preservation checks for corrected text."""


MAX_REDUCTION_RATIO = 0.35
MAX_ADDITION_RATIO = 0.50


def _paragraph_count(text):
    return len([part for part in text.split("\n\n") if part.strip()])


def validate_preservation(original_text, corrected_text):
    """Validate that corrected text appears to preserve original content."""
    warnings = []

    if not corrected_text or not corrected_text.strip():
        warnings.append("Empty corrected output detected")

    original_length = len(original_text)
    corrected_length = len(corrected_text)

    if original_length > 0:
        reduction_ratio = (original_length - corrected_length) / original_length
        addition_ratio = (corrected_length - original_length) / original_length

        if reduction_ratio > MAX_REDUCTION_RATIO:
            warnings.append("Large text reduction detected")

        if addition_ratio > MAX_ADDITION_RATIO:
            warnings.append("Large amount of added text detected")

    original_paragraphs = _paragraph_count(original_text)
    corrected_paragraphs = _paragraph_count(corrected_text)

    if original_paragraphs > 1 and corrected_paragraphs < original_paragraphs:
        warnings.append("Missing paragraphs detected")

    if original_text and corrected_text:
        unique_original_chars = set(original_text)
        unique_corrected_chars = set(corrected_text)
        lost_chars = unique_original_chars - unique_corrected_chars
        meaningful_lost_chars = {char for char in lost_chars if not char.isspace()}

        if len(meaningful_lost_chars) > max(10, len(unique_original_chars) * 0.30):
            warnings.append("Character loss detected")

    return {
        "valid": not warnings,
        "warnings": warnings,
    }
