"""Editorial polish stage for readable sermon DOCX output."""

from modules.text_chunker import chunk_text
from modules.resource_path import resource_path


POLISH_PROMPT_PATH = resource_path("prompts/polish_prompt.txt")
DEFAULT_POLISH_CHUNK_LENGTH = 2500
MIN_KEEP_RATIO = 0.40


def load_polish_prompt():
    """Load the editorial polish prompt used by the AI provider."""
    return POLISH_PROMPT_PATH.read_text(encoding="utf-8").strip()


def _merge_polished_chunks(chunks):
    parts = [part.strip() for part in chunks if part and part.strip()]
    return "\n\n".join(parts)


def _chunk_instruction(index, total):
    if index == 0:
        return (
            "This is the beginning of the sermon. "
            "Start with a short title line if a Bible chapter can be identified.\n\n"
            "Sermon text:\n"
        )
    return (
        f"This is continuation chunk {index + 1} of {total}. "
        "Do not invent a title. Continue polishing body paragraphs only.\n\n"
        "Sermon text:\n"
    )


def polish_sermon_text(text, provider, max_length=DEFAULT_POLISH_CHUNK_LENGTH):
    """Polish corrected sermon text for punctuation, paragraphs, and filler cleanup."""
    if not text or not text.strip():
        return {
            "polished_text": text or "",
            "success": False,
            "chunks_processed": 0,
            "warnings": ["Empty text cannot be polished."],
        }

    if provider is None or not hasattr(provider, "generate"):
        return {
            "polished_text": text,
            "success": False,
            "chunks_processed": 0,
            "warnings": ["A valid AI provider is required."],
        }

    prompt = load_polish_prompt()
    original_chunks = chunk_text(text, max_length=max_length)
    polished_chunks = []
    warnings = []

    for index, chunk in enumerate(original_chunks):
        content = _chunk_instruction(index, len(original_chunks)) + chunk
        try:
            polished_chunk = provider.generate(prompt, content)
            if not isinstance(polished_chunk, str) or not polished_chunk.strip():
                raise ValueError("Polish returned empty text")
            polished_chunks.append(polished_chunk)
        except Exception as error:
            polished_chunks.append(chunk)
            warnings.append(f"Chunk {index + 1} polish failed, original chunk preserved: {error}")

    if warnings:
        return {
            "polished_text": text,
            "success": False,
            "chunks_processed": len(original_chunks),
            "warnings": warnings,
        }

    polished_text = _merge_polished_chunks(polished_chunks)

    if not polished_text.strip():
        return {
            "polished_text": text,
            "success": False,
            "chunks_processed": len(original_chunks),
            "warnings": warnings + ["Polish returned empty text, original preserved."],
        }

    if len(polished_text) < len(text) * MIN_KEEP_RATIO:
        return {
            "polished_text": text,
            "success": False,
            "chunks_processed": len(original_chunks),
            "warnings": warnings + ["Polish reduced text too aggressively, original preserved."],
        }

    return {
        "polished_text": polished_text,
        "success": True,
        "chunks_processed": len(original_chunks),
        "warnings": warnings,
    }
