"""Paragraph optimization for audio sermon DOCX output."""

import re


SENTENCE_PATTERN = re.compile(r"[^。！？!?]+[。！？!?]?")
MAX_SENTENCES_PER_PARAGRAPH = 4


def _split_sentences(text):
    return [match.group(0).strip() for match in SENTENCE_PATTERN.finditer(text) if match.group(0).strip()]


def _is_boundary(paragraph):
    stripped = paragraph.strip()
    if not stripped:
        return False

    return (
        stripped.endswith(":")
        or stripped.endswith("：")
        or stripped.startswith(("经文", "读经", "祷告", "一、", "二、", "三、", "四、", "五、"))
        or len(stripped) <= 12 and not re.search(r"[。！？!?]", stripped)
    )


def optimize_audio_paragraphs(text):
    """Return readable, paper-saving paragraphs without changing content."""
    if not text or not text.strip():
        return []

    source_paragraphs = [part.strip() for part in re.split(r"\n\s*\n|\n", text) if part.strip()]
    optimized = []
    sentence_buffer = []

    def flush_buffer():
        while sentence_buffer:
            group = sentence_buffer[:MAX_SENTENCES_PER_PARAGRAPH]
            del sentence_buffer[:MAX_SENTENCES_PER_PARAGRAPH]
            optimized.append("".join(group))

    for paragraph in source_paragraphs:
        if _is_boundary(paragraph):
            flush_buffer()
            optimized.append(paragraph)
            continue

        sentences = _split_sentences(paragraph)
        if not sentences:
            sentence_buffer.append(paragraph)
        else:
            sentence_buffer.extend(sentences)

        if len(sentence_buffer) >= MAX_SENTENCES_PER_PARAGRAPH:
            flush_buffer()

    flush_buffer()
    return optimized
