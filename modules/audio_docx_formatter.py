"""Audio sermon DOCX generation with paper-saving formatting."""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import RGBColor

from modules.paragraph_optimizer import optimize_audio_paragraphs


def _apply_black_text(paragraph):
    for run in paragraph.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)
        run.font.highlight_color = WD_COLOR_INDEX.AUTO


def _apply_audio_paragraph_format(paragraph):
    paragraph_format = paragraph.paragraph_format
    paragraph_format.space_before = None
    paragraph_format.space_after = None
    paragraph_format.line_spacing = None
    _apply_black_text(paragraph)


def generate_audio_docx(text, template_path, output_path):
    """Generate an audio sermon DOCX from corrected text and the audio template."""
    template = Path(template_path)
    output = Path(output_path)

    if not template.exists():
        raise FileNotFoundError(f"Template file not found: {template}")

    paragraphs = optimize_audio_paragraphs(text)
    output.parent.mkdir(parents=True, exist_ok=True)

    document = Document(template)
    base_style = document.paragraphs[-1].style if document.paragraphs else None

    for paragraph_text in paragraphs:
        paragraph = document.add_paragraph(style=base_style)
        paragraph.add_run(paragraph_text)
        _apply_audio_paragraph_format(paragraph)

    document.save(output)

    if not output.exists():
        raise RuntimeError(f"DOCX output was not created: {output}")

    Document(output)

    return {
        "output_path": str(output),
        "success": True,
        "paragraphs_inserted": len(paragraphs),
    }
