"""Build reusable style mappings from DOCX templates."""

import json
from collections import Counter
from pathlib import Path

from modules.image_docx_analyzer import analyze_image_template


BASE_DIR = Path(__file__).resolve().parent.parent
STYLE_DATABASE_PATH = BASE_DIR / "database" / "docx_styles.json"


def _first_present_run(runs):
    for run in runs:
        if any(run.get(key) is not None for key in ("font", "size", "color", "bold", "italic", "underline")):
            return run
    return {}


def _most_common(values):
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return Counter(filtered).most_common(1)[0][0]


def build_style_mapping(template_path):
    """Extract reusable style definitions from the image template."""
    analysis = analyze_image_template(template_path)
    runs = analysis["runs"]
    styles = analysis["styles"]
    format_patterns = analysis["format_patterns"]

    first_run = _first_present_run(runs)
    body_style_name = _most_common([pattern.get("style") for pattern in format_patterns])
    body_runs = [run for run in runs if run.get("text", "").strip()]

    mapping = {
        "template": analysis["filename"],
        "title_style": {
            "style": format_patterns[0]["style"] if format_patterns else None,
            "font": first_run.get("font"),
            "size": first_run.get("size"),
            "color": first_run.get("color"),
            "bold": first_run.get("bold"),
            "italic": first_run.get("italic"),
            "underline": first_run.get("underline"),
        },
        "body_style": {
            "style": body_style_name,
            "font": _most_common([run.get("font") for run in body_runs]),
            "size": _most_common([run.get("size") for run in body_runs]),
            "color": _most_common([run.get("color") for run in body_runs]),
            "bold": _most_common([run.get("bold") for run in body_runs]),
            "italic": _most_common([run.get("italic") for run in body_runs]),
            "underline": _most_common([run.get("underline") for run in body_runs]),
        },
        "verse_style": {
            "style": body_style_name,
            "font": _most_common([run.get("font") for run in body_runs]),
            "size": _most_common([run.get("size") for run in body_runs]),
            "color": _most_common([run.get("color") for run in body_runs]),
        },
        "styles": styles,
        "colors": analysis["colors"],
        "fonts": analysis["fonts"],
        "sections": analysis["sections"],
    }

    return mapping


def save_style_mapping(template_name, style_mapping, database_path=STYLE_DATABASE_PATH):
    """Save extracted style mapping for future rendering phases."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        database = json.loads(path.read_text(encoding="utf-8-sig"))
    else:
        database = {}

    database[template_name] = {
        "styles": style_mapping.get("styles", []),
        "colors": style_mapping.get("colors", []),
        "fonts": style_mapping.get("fonts", []),
        "title_style": style_mapping.get("title_style", {}),
        "body_style": style_mapping.get("body_style", {}),
        "verse_style": style_mapping.get("verse_style", {}),
    }

    path.write_text(json.dumps(database, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
