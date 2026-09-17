"""Image DOCX rendering using template-derived style mappings."""

from pathlib import Path
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor


BODY_SIDE_MARGIN_INCHES = 0.85
HEADING_LINE_PATTERN = re.compile(r"^.{1,24}[：:]$")
PARAGRAPH_START_PATTERN = re.compile(
    r"^(?:\d+[:：]\d+|[①②③④⑤⑥⑦⑧⑨⑩]|[一二三四五六七八九十]+[、.．])"
)

def _clear_template_body(document):
    """Remove sample content but retain the template body properties and sections."""
    body = document._element.body
    section_properties = body.sectPr
    for child in list(body):
        if child is not section_properties:
            body.remove(child)


def _insert_processed_text(document, structure, style_mapping):
    """Insert analyzed text into the template using run-level styles."""
    title_style = style_mapping.get("title_style", {})
    body_style = style_mapping.get("body_style", {})
    verse_style = style_mapping.get("verse_style", body_style)

    inserted = []
    for text in structure["title"]:
        inserted.append(_add_styled_paragraph(document, text, title_style))
    for text in structure["headings"]:
        inserted.append(_add_styled_paragraph(document, text, title_style))
    for text in structure["scripture_references"]:
        inserted.append(_add_styled_paragraph(document, text, verse_style))
    for text in structure["body"]:
        inserted.append(_add_styled_paragraph(document, text, body_style))
    return inserted


def _insert_exact_text(document, text, style_mapping):
    """Insert source text as natural paragraphs without changing character order."""
    body_style = dict(style_mapping.get("body_style", {}))
    body_style["color"] = "000000"
    inserted = []
    for paragraph_text in paragraphs_from_text(text):
        paragraph = _add_styled_paragraph(document, paragraph_text, body_style)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.space_after = Pt(6)
        paragraph.paragraph_format.line_spacing = 1.25
        inserted.append(paragraph)
    return inserted


def paragraphs_from_text(text):
    """Merge OCR wrap lines, retaining blank-line and semantic paragraph breaks."""
    lines = str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    paragraphs = []
    current = []

    def flush():
        if current:
            paragraphs.append("".join(current))
            current.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if HEADING_LINE_PATTERN.fullmatch(stripped):
            flush()
            paragraphs.append(stripped)
            continue
        if PARAGRAPH_START_PATTERN.match(stripped):
            flush()
        current.append(stripped)
    flush()
    return paragraphs


def prepare_image_document(text, style_mapping, template_path):
    """Load image template and prepare insertion metadata without rendering final output."""
    path = Path(template_path)

    if not path.exists():
        raise FileNotFoundError(f"Template file not found: {path}")

    document = Document(path)
    insertion_points = [
        {
            "paragraph_index": index,
            "style": paragraph.style.name if paragraph.style else None,
            "text_preview": paragraph.text[:80],
        }
        for index, paragraph in enumerate(document.paragraphs)
    ]

    return {
        "document": document,
        "template_path": str(path),
        "text": text,
        "style_mapping": style_mapping,
        "insertion_points": insertion_points,
        "ready": True,
    }


def _rgb_color(value):
    if not value:
        return None

    value = str(value).replace("#", "")
    if len(value) != 6:
        return None

    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _apply_run_style(run, style_definition):
    if not style_definition:
        return

    if style_definition.get("font"):
        run.font.name = style_definition["font"]

    if style_definition.get("size"):
        run.font.size = Pt(float(style_definition["size"]))

    color = _rgb_color(style_definition.get("color"))
    if color is not None:
        run.font.color.rgb = color

    if style_definition.get("bold") is not None:
        run.bold = style_definition["bold"]

    if style_definition.get("italic") is not None:
        run.italic = style_definition["italic"]

    if style_definition.get("underline") is not None:
        run.underline = style_definition["underline"]


def _add_styled_paragraph(document, text, style_definition):
    style_name = style_definition.get("style") if style_definition else None

    try:
        paragraph = document.add_paragraph(style=style_name)
    except (KeyError, ValueError):
        paragraph = document.add_paragraph()

    run = paragraph.add_run(text)
    _apply_run_style(run, style_definition)
    return paragraph


def generate_image_docx(text, style_mapping, template_path, output_path, structure=None):
    """Generate a DOCX with the corrected text in exact source-line order."""
    template = Path(template_path)
    output = Path(output_path)

    if not template.exists():
        raise FileNotFoundError(f"Template file not found: {template}")

    output.parent.mkdir(parents=True, exist_ok=True)
    document = Document(template)
    for section in document.sections:
        section.left_margin = Inches(BODY_SIDE_MARGIN_INCHES)
        section.right_margin = Inches(BODY_SIDE_MARGIN_INCHES)
    _clear_template_body(document)
    inserted = _insert_exact_text(document, text, style_mapping)
    if not inserted:
        raise ValueError("Image text is empty; refusing to generate an unchanged template")

    document.save(output)

    if not output.exists():
        raise RuntimeError(f"DOCX output was not created: {output}")

    verified_document = Document(output)
    expected_lines = paragraphs_from_text(text)
    actual_lines = [paragraph.text for paragraph in verified_document.paragraphs]
    if actual_lines != expected_lines:
        output.unlink(missing_ok=True)
        raise RuntimeError("Saved DOCX content does not exactly match the corrected text")

    return {
        "output_path": str(output),
        "success": True,
        "paragraphs_inserted": len(inserted),
    }
