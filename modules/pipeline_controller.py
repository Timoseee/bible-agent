"""Final automatic processing pipeline controller."""

import re
import logging
import gc
from datetime import datetime
from pathlib import Path

from modules.ai_provider import create_ai_provider
from modules.audio_docx_formatter import generate_audio_docx
from modules.audio_transcriber import transcribe_audio
from modules.config_loader import load_config
from modules.correction_engine import correct_image_text_strict, correct_with_bible_check
from modules.full_text_auditor import audit_paragraphs
from modules.image_docx_renderer import generate_image_docx
from modules.image_docx_renderer import paragraphs_from_text
from modules.image_ocr import SUPPORTED_IMAGE_EXTENSIONS, extract_text_from_images
from modules.input_classifier import classify_input
from modules.paragraph_optimizer import build_audio_output_stem
from modules.polish_engine import polish_sermon_text
from modules.style_mapper import build_style_mapping
from modules.template_manager import get_template_path
from modules.text_cleaning_pipeline import clean_image_ocr_text, clean_transcript_text
from modules.resource_path import writable_path
from modules.local_ocr_provider import RapidOCRProvider


OUTPUT_DOCX_DIR = writable_path("output/docx")
LOGGER = logging.getLogger(__name__)
IMAGE_PLACEHOLDER_PATTERN = re.compile(r"\[IMAGE_\d+\]\s*")


def _remove_image_placeholders(text):
    """Remove OCR transport markers before text cleaning and correction."""
    cleaned = IMAGE_PLACEHOLDER_PATTERN.sub("", text or "")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _get_ocr_text(ocr_result):
    """Extract real OCR text from per-image results, excluding transport markers."""
    results = ocr_result.get("results", []) or []
    result_texts = [
        str(result.get("text", "")).strip()
        for result in results
        if result.get("success") and str(result.get("text", "")).strip()
    ]
    if result_texts:
        return "\n\n".join(result_texts)
    return _remove_image_placeholders(ocr_result.get("text", ""))


def _default_provider():
    return create_ai_provider(load_config())


def _default_image_text_provider():
    return create_ai_provider(load_config(), provider_name="deepseek")


def _default_vision_provider():
    config = load_config()
    provider_name = config.get("local_ocr_provider", "rapidocr")
    if provider_name != "rapidocr":
        raise RuntimeError(f"Unsupported local OCR provider: {provider_name}")
    return RapidOCRProvider()


def _safe_filename(path, prefix):
    stem = Path(path).stem or "folder"
    candidate = OUTPUT_DOCX_DIR / f"{prefix}_{stem}.docx"
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        alternate = OUTPUT_DOCX_DIR / f"{prefix}_{stem}_{index}.docx"
        if not alternate.exists():
            return alternate
        index += 1


def _image_output_path():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = OUTPUT_DOCX_DIR / f"图片文本_{timestamp}.docx"
    index = 2
    while candidate.exists():
        candidate = OUTPUT_DOCX_DIR / f"图片文本_{timestamp}_{index}.docx"
        index += 1
    return candidate


def _sanitize_filename(name):
    cleaned = re.sub(r'[<>:"/\\|?*]', "", str(name)).strip()
    return cleaned or "音频文本"


def _audio_output_path(text, audio_path):
    stem = build_audio_output_stem(text)
    if not stem:
        stem = f"音频文本_{Path(audio_path).stem}"
    candidate = OUTPUT_DOCX_DIR / f"{_sanitize_filename(stem)}.docx"
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        alternate = OUTPUT_DOCX_DIR / f"{_sanitize_filename(stem)}_{index}.docx"
        if not alternate.exists():
            return alternate
        index += 1


def _success(input_path, input_type, output_path, steps):
    return {
        "success": True,
        "input": str(input_path),
        "input_type": input_type,
        "output": str(output_path),
        "steps": steps,
    }


def _failure(input_path, input_type, step, error):
    LOGGER.error("Pipeline failed at step %s: %s", step, error)
    return {
        "success": False,
        "input": str(input_path),
        "input_type": input_type,
        "step": step,
        "error": str(error),
    }


def process_input(input_path, provider=None, vision_provider=None, *, cleanup_images=True):
    """Automatically route input to audio or image workflow."""
    try:
        classification = classify_input(input_path)
    except Exception as error:
        return _failure(input_path, "error", "input_detection", error)
    input_type = classification["type"]

    if input_type == "audio":
        return process_audio_input(input_path, provider=provider)

    if input_type in {"image", "image_folder"}:
        return process_image_input(
            input_path,
            provider=provider,
            vision_provider=vision_provider,
            cleanup_images=cleanup_images,
        )

    return _failure(input_path, input_type, "input_detection", classification.get("error", "Unsupported input"))


def process_audio_input(audio_path, provider=None):
    """Run audio workflow from transcription through audio DOCX generation."""
    steps = []

    try:
        provider = provider or _default_provider()
    except Exception as error:
        return _failure(audio_path, "audio", "configuration", error)

    try:
        transcription = transcribe_audio(audio_path)
        steps.append("Whisper transcription completed")
    except Exception as error:
        return _failure(audio_path, "audio", "transcription", error)

    try:
        cleaned = clean_transcript_text(transcription.get("text", ""))
        if not cleaned["cleaned_text"]:
            return _failure(audio_path, "audio", "text_cleaning", "Whisper returned no readable text")
        transcript_text = cleaned["cleaned_text"]
        steps.append("Text cleaning completed")
    except Exception as error:
        return _failure(audio_path, "audio", "text_cleaning", error)

    try:
        correction = correct_with_bible_check(transcript_text, provider)
        if correction.get("approved") is not True:
            return _failure(
                audio_path, "audio", "correction",
                f"Correction was not approved: {correction.get('review', '')}. "
                + "; ".join(correction.get("warnings", [])),
            )
        final_text = correction["final_text"]
        steps.append("Bible checking completed")
        steps.append("DeepSeek/OpenAI correction completed")
        steps.append("Review agent completed")
    except Exception as error:
        return _failure(audio_path, "audio", "correction", error)

    try:
        polish = polish_sermon_text(final_text, provider)
        if not polish["success"]:
            return _failure(
                audio_path, "audio", "polish",
                "; ".join(polish.get("warnings", [])) or "Editorial polish failed",
            )
        final_text = clean_transcript_text(polish["polished_text"])["cleaned_text"]
        steps.append("Editorial polish completed")
    except Exception as error:
        return _failure(audio_path, "audio", "polish", error)

    try:
        output_path = _audio_output_path(final_text, audio_path)
        generate_audio_docx(final_text, get_template_path("audio"), output_path)
        steps.append("Audio DOCX generated")
    except Exception as error:
        return _failure(audio_path, "audio", "docx_generation", error)

    return _success(audio_path, "audio", output_path, steps)


def _collect_image_paths(input_path):
    path = Path(input_path)

    if path.is_file():
        return [path]

    paths = [
        item
        for item in path.iterdir()
        if item.is_file() and item.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    ]
    return sorted(paths, key=_natural_path_key)


def _natural_path_key(path):
    return [
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", Path(path).name)
    ]


def _notify(callback, percent, message):
    if callback is not None:
        callback(percent, message)


def _image_failure(input_path, step, error, details):
    result = _failure(input_path, "image", step, error)
    result.update(details)
    return result


def _recycle_images(image_paths):
    try:
        from send2trash import send2trash
    except ImportError as error:
        return [f"Recycle Bin support is unavailable: {error}"]

    errors = []
    for image_path in image_paths:
        try:
            send2trash(str(image_path))
        except Exception as error:
            errors.append(f"{Path(image_path).name}: {error}")
    return errors


def process_image_input(
    input_path,
    provider=None,
    vision_provider=None,
    *,
    cleanup_images=True,
    progress_callback=None,
):
    """Run image workflow from ordering through image DOCX generation."""
    steps = []
    details = {
        "images_total": 0,
        "images_ocr_completed": 0,
        "failed_images": [],
        "cleanup_errors": [],
        "preserved_chunks": [],
        "full_audit_candidates": 0,
        "full_audit_applied": 0,
        "full_audit_rejected": 0,
        "full_audit_rounds": 0,
        "audit_warnings": [],
    }
    config = load_config()

    try:
        image_paths = _collect_image_paths(input_path)
        if not image_paths:
            return _image_failure(
                input_path, "image_collection", "No supported images found", details
            )
        details["images_total"] = len(image_paths)
        steps.append("Images collected")
        steps.append("Natural filename ordering completed")
        _notify(progress_callback, 10, f"已读取 {len(image_paths)} 张图片")
    except Exception as error:
        return _image_failure(input_path, "image_collection", error, details)

    try:
        vision_provider = vision_provider or _default_vision_provider()
    except Exception as error:
        return _image_failure(input_path, "configuration", error, details)

    try:
        LOGGER.debug("Before OCR: number of images=%d", len(image_paths))
        _notify(progress_callback, 20, "正在进行本地 OCR")
        ocr = extract_text_from_images(image_paths, vision_provider)
        results = ocr.get("results", [])
        details["images_ocr_completed"] = sum(
            1 for result in results if result.get("success")
        )
        minimum_characters = config.get("ocr_min_characters", 5)
        minimum_confidence = config.get("ocr_min_confidence", 0.55)
        failed = []
        for result in results:
            result_text = str(result.get("text", "") or "")
            character_count = result.get("character_count")
            if character_count is None:
                character_count = sum(1 for character in result_text if character.isalnum())
            confidence = result.get("confidence")
            if confidence is None:
                confidence = 1.0 if result.get("success") and result_text.strip() else 0.0
            reasons = []
            if not result.get("success"):
                reasons.append(result.get("error") or "OCR failed")
            if int(character_count) < minimum_characters:
                reasons.append(f"fewer than {minimum_characters} readable characters")
            if float(confidence) < minimum_confidence:
                reasons.append(f"confidence below {minimum_confidence:.2f}")
            if reasons:
                failed.append(
                    {"filename": result.get("filename", ""), "reason": "; ".join(reasons)}
                )
        if failed:
            details["failed_images"] = failed
            names = ", ".join(item["filename"] for item in failed)
            return _image_failure(
                input_path,
                "OCR_quality",
                f"OCR quality check failed: {names}",
                details,
            )
        ocr_text = _get_ocr_text(ocr)
        LOGGER.debug("After OCR: text length=%d", len(ocr_text))
        steps.append("OCR completed")
    except Exception as error:
        return _image_failure(input_path, "OCR", error, details)

    if getattr(vision_provider, "provider_name", "") == "rapidocr":
        del vision_provider
        gc.collect()

    try:
        cleaned = clean_image_ocr_text(ocr_text)
        if not cleaned["cleaned_text"]:
            return _image_failure(
                input_path, "OCR", "OCR returned no readable text", details
            )
        steps.append("Image export labels removed")
    except Exception as error:
        return _image_failure(input_path, "watermark_cleaning", error, details)

    try:
        _notify(progress_callback, 55, "正在使用 DeepSeek V4 Flash 校对和复核")
        provider = provider or _default_image_text_provider()
        correction = correct_image_text_strict(cleaned["cleaned_text"], provider)
        if not correction.get("success"):
            return _image_failure(
                input_path,
                "correction",
                correction.get("error", "DeepSeek correction failed"),
                details,
            )
        final_text = correction["final_text"]
        details["preserved_chunks"] = correction.get("preserved_chunks", [])
        LOGGER.debug("After correction: text length=%d", len(final_text))
        if details["preserved_chunks"]:
            steps.append(
                "Correction and review completed; disputed chunks preserved unchanged"
            )
        else:
            steps.append("Correction and review completed")
    except Exception as error:
        return _image_failure(input_path, "correction", error, details)

    try:
        _notify(progress_callback, 72, "正在使用 DeepSeek 进行两轮全文查漏")
        audit = audit_paragraphs(
            paragraphs_from_text(final_text),
            provider,
            rounds=2,
            max_characters=config.get("full_audit_window_characters", 6000),
            overlap_characters=config.get("full_audit_overlap_characters", 600),
            minimum_confidence=config.get("full_audit_min_confidence", 0.92),
        )
        final_text = audit["final_text"]
        for key in (
            "full_audit_candidates",
            "full_audit_applied",
            "full_audit_rejected",
            "full_audit_rounds",
            "audit_warnings",
        ):
            details[key] = audit[key]
        steps.append("Two-round DeepSeek full-text audit completed")
    except Exception as error:
        return _image_failure(input_path, "full_audit", error, details)

    temporary_path = None
    try:
        _notify(progress_callback, 90, "正在生成并验证 Word 文档")
        LOGGER.debug("Before DOCX generation: final text preview=%r", final_text[:200])
        output_path = _image_output_path()
        temporary_path = output_path.with_name(f".{output_path.stem}.tmp.docx")
        style_mapping = build_style_mapping(get_template_path("image"))
        generate_image_docx(
            final_text,
            style_mapping,
            get_template_path("image"),
            temporary_path,
        )
        temporary_path.replace(output_path)
        steps.append("Image DOCX generated")
    except Exception as error:
        LOGGER.exception("Image DOCX generation failed for %s", input_path)
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        return _image_failure(input_path, "docx_generation", error, details)

    if cleanup_images:
        _notify(progress_callback, 97, "正在把原图移入 Windows 回收站")
        details["cleanup_errors"] = _recycle_images(image_paths)
        if details["cleanup_errors"]:
            steps.append("DOCX completed; some source images could not be recycled")
        else:
            steps.append("Source images moved to Recycle Bin")

    result = _success(input_path, "image", output_path, steps)
    result.update(details)
    _notify(progress_callback, 100, "处理完成")
    return result
