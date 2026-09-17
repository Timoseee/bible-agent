"""Correction engine for proofreading short and long text."""

import re

from modules.bible_checker import check_bible_terms, load_bible_database
from modules.bible_context_builder import build_bible_context
from modules.correction_validator import validate_preservation
from modules.review_agent import review_correction
from modules.text_chunker import DEFAULT_MAX_LENGTH, chunk_text
from modules.text_merger import merge_chunks
from modules.resource_path import resource_path


CORRECTION_PROMPT_PATH = resource_path("prompts/correction_prompt.txt")


def _restore_boundary_whitespace(original, corrected):
    """Restore source-owned separators around a model-corrected chunk."""
    leading = re.match(r"^\s*", original or "").group(0)
    trailing = re.search(r"\s*$", original or "").group(0)
    return leading + str(corrected or "").strip() + trailing


def _same_line_layout(original, corrected):
    """Require identical line counts and blank-line positions."""
    original_lines = str(original or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    corrected_lines = str(corrected or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(original_lines) != len(corrected_lines):
        return False
    return [not line.strip() for line in original_lines] == [
        not line.strip() for line in corrected_lines
    ]


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
        except Exception as error:
            corrected_chunks.append(chunk)
            warnings.append(f"Chunk {index} correction failed, original text preserved: {error}")

    return {
        "corrected_text": merge_chunks(corrected_chunks),
        "chunks_processed": len(original_chunks),
        "success": not warnings,
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


def correct_image_text_strict(text, provider, max_length=DEFAULT_MAX_LENGTH):
    """Correct and independently review every image-text chunk without fallback output."""
    if not text or not text.strip():
        return {
            "success": False,
            "final_text": "",
            "error": "OCR text is empty.",
            "chunks_processed": 0,
        }
    if provider is None or not hasattr(provider, "generate"):
        return {
            "success": False,
            "final_text": "",
            "error": "A valid DeepSeek provider is required.",
            "chunks_processed": 0,
        }

    prompt = load_correction_prompt()
    original_chunks = chunk_text(text, max_length=max_length)
    corrected_chunks = []
    preserved_chunks = []
    bible_database = load_bible_database()

    for index, chunk in enumerate(original_chunks, start=1):
        bible_result = check_bible_terms(chunk, bible_database)
        bible_context = build_bible_context(bible_result["issues"])
        base_chunk_prompt = prompt
        if bible_context:
            base_chunk_prompt += "\n\nReference suggestions for this chunk:\n" + bible_context

        corrected = ""
        review = {}
        retry_feedback = ""
        previous_correction = ""
        for correction_attempt in range(2):
            chunk_prompt = base_chunk_prompt
            if correction_attempt:
                chunk_prompt += (
                    "\n\nThe previous correction was rejected by an independent reviewer. "
                    "Correct the ORIGINAL text again. Revert every disputed change, "
                    "especially pronouns, speaker perspective, theology, and meaning. "
                    "Only retain indisputable OCR, character, punctuation, or Bible-name fixes.\n"
                    f"Reviewer feedback:\n{retry_feedback}\n\n"
                    f"Rejected correction for reference:\n{previous_correction}"
                )
            try:
                corrected = provider.generate(chunk_prompt, chunk)
            except Exception as error:
                return {
                    "success": False,
                    "final_text": "",
                    "error": f"DeepSeek correction failed for chunk {index}: {error}",
                    "chunks_processed": index - 1,
                }
            corrected = _restore_boundary_whitespace(chunk, corrected)

            if not _same_line_layout(chunk, corrected):
                if correction_attempt == 0:
                    retry_feedback = (
                        "Line layout changed. Keep exactly the same number of lines, "
                        "line order, and blank-line positions as the ORIGINAL text."
                    )
                    previous_correction = corrected
                    continue
                corrected = chunk
                preserved_chunks.append(index)
                break

            validation = validate_preservation(chunk, corrected)
            if not validation["valid"]:
                if correction_attempt == 0:
                    retry_feedback = "; ".join(validation["warnings"])
                    previous_correction = corrected
                    continue
                corrected = chunk
                preserved_chunks.append(index)
                break

            try:
                review = review_correction(chunk, corrected, provider)
            except Exception as error:
                return {
                    "success": False,
                    "final_text": "",
                    "error": f"DeepSeek review failed for chunk {index}: {error}",
                    "chunks_processed": index,
                }
            if review.get("approved"):
                break
            retry_feedback = str(review.get("summary", "No summary returned"))
            if review.get("issues"):
                retry_feedback += "\n" + str(review["issues"])
            previous_correction = corrected
        else:
            corrected = chunk
            preserved_chunks.append(index)
        corrected_chunks.append(corrected)

    final_text = merge_chunks(corrected_chunks)
    final_validation = validate_preservation(text, final_text)
    if not final_validation["valid"]:
        return {
            "success": False,
            "final_text": "",
            "error": "Merged content preservation failed: "
            + "; ".join(final_validation["warnings"]),
            "chunks_processed": len(original_chunks),
        }
    return {
        "success": True,
        "final_text": final_text,
        "chunks_processed": len(original_chunks),
        "preserved_chunks": preserved_chunks,
        "error": "",
    }
