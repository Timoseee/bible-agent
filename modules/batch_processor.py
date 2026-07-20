"""Sequential batch processing preparation."""

from pathlib import Path

from modules.image_ocr import SUPPORTED_IMAGE_EXTENSIONS
from modules.pipeline_controller import process_input


def _is_image_folder(path):
    return path.is_dir() and any(
        item.is_file() and item.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS for item in path.iterdir()
    )


def process_folder(folder_path):
    """Process supported audio files and image folders sequentially."""
    folder = Path(folder_path)
    results = []

    if not folder.exists() or not folder.is_dir():
        return [{"input": str(folder), "output": "", "status": "failed", "error": "Folder not found"}]

    for item in folder.iterdir():
        if item.is_file() and item.suffix.lower() in {".mp3", ".m4a"}:
            result = process_input(item)
            results.append(
                {
                    "input": str(item),
                    "output": result.get("output", ""),
                    "status": "success" if result.get("success") else "failed",
                    "error": result.get("error", ""),
                }
            )
        elif _is_image_folder(item):
            result = process_input(item)
            results.append(
                {
                    "input": str(item),
                    "output": result.get("output", ""),
                    "status": "success" if result.get("success") else "failed",
                    "error": result.get("error", ""),
                }
            )

    return results
