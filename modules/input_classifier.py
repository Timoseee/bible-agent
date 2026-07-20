"""Input classification for supported BibleAI files and folders."""

from pathlib import Path


AUDIO_EXTENSIONS = {".mp3", ".m4a"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def classify_input(path):
    """Classify an input path as audio, image, image folder, or unsupported."""
    input_path = Path(path)

    if not input_path.exists():
        return {
            "type": "error",
            "path": str(input_path),
            "error": "Input path does not exist.",
        }

    if input_path.is_dir():
        image_files = [
            item
            for item in input_path.iterdir()
            if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS
        ]

        if image_files:
            return {
                "type": "image_folder",
                "path": str(input_path),
                "image_count": len(image_files),
            }

        return {
            "type": "unsupported",
            "path": str(input_path),
            "error": "Folder does not contain supported image files.",
        }

    extension = input_path.suffix.lower()

    if extension in AUDIO_EXTENSIONS:
        return {
            "type": "audio",
            "path": str(input_path),
            "extension": extension,
        }

    if extension in IMAGE_EXTENSIONS:
        return {
            "type": "image",
            "path": str(input_path),
            "extension": extension,
        }

    return {
        "type": "unsupported",
        "path": str(input_path),
        "extension": extension,
        "error": "Unsupported file type.",
    }
