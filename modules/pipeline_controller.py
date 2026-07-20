"""Final automatic processing pipeline controller."""

from pathlib import Path

from modules.ai_provider import create_ai_provider
from modules.audio_docx_formatter import generate_audio_docx
from modules.audio_transcriber import transcribe_audio
from modules.config_loader import load_config
from modules.correction_engine import correct_with_bible_check
from modules.image_docx_renderer import generate_image_docx
from modules.image_ocr import SUPPORTED_IMAGE_EXTENSIONS, extract_text_from_images
from modules.image_sorter import sort_images
from modules.input_classifier import classify_input
from modules.style_mapper import build_style_mapping
from modules.template_manager import get_template_path
from modules.text_cleaning_pipeline import clean_ocr_text


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DOCX_DIR = BASE_DIR / "output" / "docx"


def _default_provider():
    return create_ai_provider(load_config())


def _safe_filename(path, prefix):
    stem = Path(path).stem or "folder"
    return OUTPUT_DOCX_DIR / f"{prefix}_{stem}.docx"


def _success(input_path, input_type, output_path, steps):
    return {
        "success": True,
        "input": str(input_path),
        "input_type": input_type,
        "output": str(output_path),
        "steps": steps,
    }


def _failure(input_path, input_type, step, error):
    return {
        "success": False,
        "input": str(input_path),
        "input_type": input_type,
        "step": step,
        "error": str(error),
    }


def process_input(input_path, provider=None, vision_provider=None):
    """Automatically route input to audio or image workflow."""
    classification = classify_input(input_path)
    input_type = classification["type"]

    if input_type == "audio":
        return process_audio_input(input_path, provider=provider)

    if input_type in {"image", "image_folder"}:
        return process_image_input(input_path, provider=provider, vision_provider=vision_provider)

    return _failure(input_path, input_type, "input_detection", classification.get("error", "Unsupported input"))


def process_audio_input(audio_path, provider=None):
    """Run audio workflow from transcription through audio DOCX generation."""
    provider = provider or _default_provider()
    steps = []

    try:
        transcription = transcribe_audio(audio_path)
        steps.append("Whisper transcription completed")
    except Exception as error:
        return _failure(audio_path, "audio", "transcription", error)

    try:
        correction = correct_with_bible_check(transcription["text"], provider)
        final_text = correction["final_text"]
        steps.append("Correction and review completed")
    except Exception as error:
        return _failure(audio_path, "audio", "correction", error)

    try:
        output_path = _safe_filename(audio_path, "audio")
        generate_audio_docx(final_text, get_template_path("audio"), output_path)
        steps.append("Audio DOCX generated")
    except Exception as error:
        return _failure(audio_path, "audio", "docx_generation", error)

    return _success(audio_path, "audio", output_path, steps)


def _collect_image_paths(input_path):
    path = Path(input_path)

    if path.is_file():
        return [path]

    return [
        item
        for item in path.iterdir()
        if item.is_file() and item.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    ]


def process_image_input(input_path, provider=None, vision_provider=None):
    """Run image workflow from ordering through image DOCX generation."""
    provider = provider or _default_provider()
    vision_provider = vision_provider or provider
    steps = []

    try:
        image_paths = _collect_image_paths(input_path)
        if not image_paths:
            return _failure(input_path, "image", "image_collection", "No supported images found")
        steps.append("Images collected")
    except Exception as error:
        return _failure(input_path, "image", "image_collection", error)

    try:
        ordering = sort_images(image_paths, vision_provider)
        ordered_images = [Path(path) for path in ordering["ordered_images"]]
        steps.append("Ordering images completed")
    except Exception as error:
        return _failure(input_path, "image", "image_ordering", error)

    try:
        ocr = extract_text_from_images(ordered_images, vision_provider)
        steps.append("OCR completed")
    except Exception as error:
        return _failure(input_path, "image", "OCR", error)

    try:
        cleaned = clean_ocr_text(ocr["text"])
        steps.append("Watermark cleaning completed")
    except Exception as error:
        return _failure(input_path, "image", "watermark_cleaning", error)

    try:
        correction = correct_with_bible_check(cleaned["cleaned_text"], provider)
        final_text = correction["final_text"]
        steps.append("Correction and review completed")
    except Exception as error:
        return _failure(input_path, "image", "correction", error)

    try:
        output_path = _safe_filename(input_path, "image")
        style_mapping = build_style_mapping(get_template_path("image"))
        generate_image_docx(final_text, style_mapping, get_template_path("image"), output_path)
        steps.append("Image DOCX generated")
    except Exception as error:
        return _failure(input_path, "image", "docx_generation", error)

    return _success(input_path, "image", output_path, steps)
