"""Correction engine for proofreading short and long text."""

from pathlib import Path

from modules.bible_checker import check_bible_terms, load_bible_database
from modules.bible_context_builder import build_bible_context
from modules.correction_validator import validate_preservation
from modules.review_agent import review_correction
from modules.text_chunker import DEFAULT_MAX_LENGTH, chunk_text
from modules.text_merger import merge_chunks


BASE_DIR = Path(__file__).resolve().parent.parent
CORRECTION_PROMPT_PATH = BASE_DIR / "prompts" / "correction_prompt.txt"


def load_correction_prompt():
    """Load the correction prompt used by the AI provider."""
    return CORRECTION_PROMPT_PATH.read_text(encoding="utf-8").strip()


def correct_text(text, provider):
    """Correct raw text by sending it to the configured AI provider."""
    if provider is None or not hasattr(provider, "generate"):
        return {
            "corrected_text": "",
            "success": False,
            "error": "A valid AI provider is required.",
        }

    prompt = load_correction_prompt()
    corrected_text = provider.generate(prompt, text)

    return {
        "corrected_text": corrected_text,
        "success": True,
    }


def correct_long_text(text, provider, max_length=DEFAULT_MAX_LENGTH):
    """Correct long text by chunking, correcting, and merging safely."""
    if provider is None or not hasattr(provider, "generate"):
        return {
            "corrected_text": "",
            "chunks_processed": 0,
            "success": False,
            "warnings": ["A valid AI provider is required."],
        }

    prompt = load_correction_prompt()
    original_chunks = chunk_text(text, max_length=max_length)
    corrected_chunks = []
    warnings = []

    for index, chunk in enumerate(original_chunks, start=1):
        try:
            corrected_chunks.append(provider.generate(prompt, chunk))
        except Exception:
            corrected_chunks.append(chunk)
            warnings.append(f"Chunk {index} correction failed, original text preserved")

    return {
        "corrected_text": merge_chunks(corrected_chunks),
        "chunks_processed": len(original_chunks),
        "success": True,
        "warnings": warnings,
    }


def correct_and_review(text, provider):
    """Correct text, validate preservation, and return approved final text."""
    correction = correct_long_text(text, provider)

    if not correction["success"]:
        return {
            "final_text": text,
            "approved": False,
            "review": "Correction failed.",
            "warnings": correction.get("warnings", []),
        }

    corrected_text = correction["corrected_text"]
    validation = validate_preservation(text, corrected_text)
    warnings = list(correction.get("warnings", [])) + validation["warnings"]

    if not validation["valid"]:
        return {
            "final_text": text,
            "approved": False,
            "review": "Automatic preservation validation failed.",
            "warnings": warnings,
        }

    try:
        review = review_correction(text, corrected_text, provider)
    except Exception as error:
        return {
            "final_text": text,
            "approved": False,
            "review": f"Review failed: {error}",
            "warnings": warnings + ["Review failed, original text preserved"],
        }

    if review["approved"]:
        return {
            "final_text": corrected_text,
            "approved": True,
            "review": review,
            "warnings": warnings,
        }

    return {
        "final_text": text,
        "approved": False,
        "review": review,
        "warnings": warnings,
    }


def _approve_corrected_text(original_text, corrected_text, provider, warnings=None):
    """Validate and review corrected text, preserving original text on failure."""
    warnings = list(warnings or [])
    validation = validate_preservation(original_text, corrected_text)
    warnings.extend(validation["warnings"])

    if not validation["valid"]:
        return {
            "final_text": original_text,
            "approved": False,
            "review": "Automatic preservation validation failed.",
            "warnings": warnings,
        }

    try:
        review = review_correction(original_text, corrected_text, provider)
    except Exception as error:
        return {
            "final_text": original_text,
            "approved": False,
            "review": f"Review failed: {error}",
            "warnings": warnings + ["Review failed, original text preserved"],
        }

    if review["approved"]:
        return {
            "final_text": corrected_text,
            "approved": True,
            "review": review,
            "warnings": warnings,
        }

    return {
        "final_text": original_text,
        "approved": False,
        "review": review,
        "warnings": warnings,
    }


def correct_with_bible_check(text, provider):
    """Correct text with Bible terminology suggestions and review safeguards."""
    if provider is None or not hasattr(provider, "generate"):
        return {
            "final_text": text,
            "approved": False,
            "bible_issues": [],
            "bible_context": "",
            "review": "Correction failed.",
            "warnings": ["A valid AI provider is required."],
        }

    database = load_bible_database()
    bible_result = check_bible_terms(text, database)
    bible_issues = bible_result["issues"]
    bible_context = build_bible_context(bible_issues)
    prompt = load_correction_prompt()
    correction_content = (
        "Original text:\n"
        f"{text}\n\n"
        f"{bible_context}"
    )

    try:
        corrected_text = provider.generate(prompt, correction_content)
    except Exception as error:
        return {
            "final_text": text,
            "approved": False,
            "bible_issues": bible_issues,
            "bible_context": bible_context,
            "review": f"Correction failed: {error}",
            "warnings": ["Correction failed, original text preserved"],
        }

    result = _approve_corrected_text(text, corrected_text, provider)
    result["bible_issues"] = bible_issues
    result["bible_context"] = bible_context
    return result
