"""Content-preserving text chunking for long correction jobs."""

import re


DEFAULT_MAX_LENGTH = 3000
SENTENCE_END_PATTERN = re.compile(r"([^。！？!?]*[。！？!?])")
PARAGRAPH_SEPARATOR_PATTERN = re.compile(r"(\n\s*\n)")


def _split_by_paragraph(text):
    """Split text into paragraph-sized units while preserving separators."""
    parts = PARAGRAPH_SEPARATOR_PATTERN.split(text)
    units = []
    index = 0

    while index < len(parts):
        unit = parts[index]
        if index + 1 < len(parts) and PARAGRAPH_SEPARATOR_PATTERN.fullmatch(parts[index + 1]):
            unit += parts[index + 1]
            index += 2
        else:
            index += 1

        if unit:
            units.append(unit)

    return units


def _split_by_sentence(text):
    """Split long text by Chinese sentence punctuation while preserving text."""
    sentences = []
    cursor = 0

    for match in SENTENCE_END_PATTERN.finditer(text):
        sentence = match.group(0)
        if sentence:
            sentences.append(sentence)
        cursor = match.end()

    if cursor < len(text):
        sentences.append(text[cursor:])

    return [sentence for sentence in sentences if sentence]


def _split_by_character_length(text, max_length):
    """Split text by character length as the final fallback."""
    return [text[index : index + max_length] for index in range(0, len(text), max_length)]


def _split_oversized_unit(unit, max_length):
    if len(unit) <= max_length:
        return [unit]

    sentence_units = []
    for sentence in _split_by_sentence(unit):
        if len(sentence) <= max_length:
            sentence_units.append(sentence)
        else:
            sentence_units.extend(_split_by_character_length(sentence, max_length))

    return sentence_units


def chunk_text(text, max_length=DEFAULT_MAX_LENGTH):
    """Split text into ordered chunks without losing characters or punctuation."""
    if text == "":
        return []

    if max_length <= 0:
        raise ValueError("max_length must be greater than 0.")

    chunks = []
    current_chunk = ""

    units = []
    for paragraph_unit in _split_by_paragraph(text):
        units.extend(_split_oversized_unit(paragraph_unit, max_length))

    for unit in units:
        if not current_chunk:
            current_chunk = unit
        elif len(current_chunk) + len(unit) <= max_length:
            current_chunk += unit
        else:
            chunks.append(current_chunk)
            current_chunk = unit

    if current_chunk:
        chunks.append(current_chunk)

    return chunks
