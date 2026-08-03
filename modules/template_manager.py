"""DOCX template management for BibleAI."""

from docx import Document

from modules.docx_analyzer import analyze_template
from modules.resource_path import resource_path


TEMPLATE_DIR = resource_path("templates")
TEMPLATE_FILES = {
    "audio": TEMPLATE_DIR / "audio_template.docx",
    "image": TEMPLATE_DIR / "image_template.docx",
}


def get_template_path(template_type):
    """Return the expected path for a supported template type."""
    return TEMPLATE_FILES.get(template_type)


def template_exists(template_type):
    """Check whether the requested template file exists."""
    template_path = get_template_path(template_type)
    return bool(template_path and template_path.exists())


def load_template(template_type):
    """Load and return a DOCX template object.

    Supported template types are "audio" and "image". A clear error message is
    returned when the template type is unknown or the DOCX file is missing.
    """
    template_path = get_template_path(template_type)

    if template_path is None:
        return f"Error: unknown template type '{template_type}'. Use 'audio' or 'image'."

    if not template_path.exists():
        return f"Error: template file not found at {template_path}."

    return Document(template_path)


def get_template_info(template_type):
    """Return analyzed information for a supported template."""
    template_path = get_template_path(template_type)

    if template_path is None:
        return {
            "success": False,
            "error": f"Unknown template type '{template_type}'. Use 'audio' or 'image'.",
        }

    if not template_path.exists():
        return {
            "success": False,
            "error": f"Template file not found at {template_path}.",
        }

    info = analyze_template(template_path)
    info["success"] = True
    return info
