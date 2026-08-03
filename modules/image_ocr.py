"""Vision OCR module for extracting raw text from images."""

from pathlib import Path

from PIL import Image, UnidentifiedImageError
from modules.resource_path import resource_path


OCR_PROMPT_PATH = resource_path("prompts/ocr_prompt.txt")
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def load_ocr_prompt():
    """Load the OCR extraction prompt."""
    return OCR_PROMPT_PATH.read_text(encoding="utf-8").strip()


def _validate_image_path(image_path):
    path = Path(image_path)

    if not path.exists():
        return None, "Image file does not exist."

    if not path.is_file():
        return None, "Image path is not a file."

    if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        return None, "Unsupported image format. Use .jpg, .jpeg, or .png."

    try:
        with Image.open(path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError):
        return None, "Image file could not be read."

    return path, None


def extract_text_from_image(image_path, provider):
    """Extract raw visible text from a single image."""
    path, error = _validate_image_path(image_path)
    if error:
        return {
            "filename": Path(image_path).name,
            "text": "",
            "success": False,
            "error": error,
        }

    if provider is None or not hasattr(provider, "generate_from_image"):
        return {
            "filename": path.name,
            "text": "",
            "success": False,
            "error": "A vision-capable provider is required.",
        }

    prompt = load_ocr_prompt()
    text = provider.generate_from_image(prompt, path)

    return {
        "filename": path.name,
        "text": text or "",
        "success": True,
    }


def extract_text_from_images(image_paths, provider):
    """Extract raw text from images in the given order."""
    combined_parts = []
    results = []

    for index, image_path in enumerate(image_paths, start=1):
        result = extract_text_from_image(image_path, provider)
        results.append(result)
        combined_parts.extend(
            [
                f"[IMAGE_{index:03d}]",
                result["text"] if result["success"] else "",
            ]
        )

    return {
        "text": "\n\n".join(combined_parts),
        "images_processed": len(image_paths),
        "results": results,
    }
