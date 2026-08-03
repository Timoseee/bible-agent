"""Startup checks used by the desktop application."""

from modules.resource_path import resource_path, writable_path


REQUIRED_RESOURCES = (
    ("templates", "templates"),
    ("bible database", "database/bible_terms.json"),
    ("correction prompt", "prompts/correction_prompt.txt"),
    ("review prompt", "prompts/review_prompt.txt"),
)


def validate_startup_resources():
    errors = [f"Missing {label}: {path}" for label, path in REQUIRED_RESOURCES if not resource_path(path).exists()]
    output_dir = writable_path("output")
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        probe = output_dir / ".bibleai_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as error:
        errors.append(f"Output folder is not writable: {error}")
    return errors
