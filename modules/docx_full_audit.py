"""Apply conservative full-text auditing to an existing image DOCX."""

from pathlib import Path

from docx import Document
from docx.shared import RGBColor

from modules.full_text_auditor import audit_paragraphs


def _replace_paragraph_text(paragraph, text):
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)
    for run in paragraph.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)


def write_audited_docx(source_path, output_path, audited_paragraphs):
    """Write already-audited paragraphs to a verified copy of the source DOCX."""
    source = Path(source_path)
    output = Path(output_path)
    document = Document(source)
    audited_paragraphs = [str(value) for value in audited_paragraphs]
    if len(audited_paragraphs) != len(document.paragraphs):
        raise RuntimeError("Full audit changed the DOCX paragraph count")

    for paragraph, text in zip(document.paragraphs, audited_paragraphs):
        _replace_paragraph_text(paragraph, text)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.stem}.tmp.docx")
    document.save(temporary)
    verified = Document(temporary)
    if [paragraph.text for paragraph in verified.paragraphs] != audited_paragraphs:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("Saved DOCX text does not match the audited paragraphs")
    for section in verified.sections:
        if section.left_margin != section.right_margin:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("Saved DOCX no longer has equal left and right margins")
    if any(
        run.text and run.font.color.rgb != RGBColor(0, 0, 0)
        for paragraph in verified.paragraphs
        for run in paragraph.runs
    ):
        temporary.unlink(missing_ok=True)
        raise RuntimeError("Saved DOCX contains non-black text")
    temporary.replace(output)
    return output


def audit_existing_docx(source_path, output_path, provider, **audit_options):
    """Audit an existing DOCX and save a verified, formatting-preserving copy."""
    source = Path(source_path)
    output = Path(output_path)
    if not source.exists():
        raise FileNotFoundError(f"Source DOCX not found: {source}")

    document = Document(source)
    original_paragraphs = [paragraph.text for paragraph in document.paragraphs]
    audit = audit_paragraphs(original_paragraphs, provider, **audit_options)
    write_audited_docx(source, output, audit["paragraphs"])
    result = dict(audit)
    result["output_path"] = str(output)
    return result
