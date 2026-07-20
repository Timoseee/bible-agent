"""Audio metadata analysis for BibleAI inputs."""

from pathlib import Path

from mutagen import File


MAX_DURATION_MINUTES = 120


def analyze_audio(audio_path):
    """Analyze audio metadata without transcribing audio content."""
    path = Path(audio_path)
    size_bytes = path.stat().st_size if path.exists() else 0
    extension = path.suffix.lower()

    result = {
        "filename": path.name,
        "file_type": extension,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "duration_seconds": None,
        "duration_minutes": None,
        "within_limit": False,
        "warning": None,
    }

    if not path.exists():
        result["warning"] = "Audio file does not exist."
        return result

    audio = File(path)
    if audio is None or not hasattr(audio, "info") or not hasattr(audio.info, "length"):
        result["warning"] = "Audio metadata could not be read."
        return result

    duration_seconds = float(audio.info.length)
    duration_minutes = duration_seconds / 60
    within_limit = duration_minutes <= MAX_DURATION_MINUTES

    result.update(
        {
            "duration_seconds": round(duration_seconds, 2),
            "duration_minutes": round(duration_minutes, 2),
            "within_limit": within_limit,
        }
    )

    if not within_limit:
        result["warning"] = "Audio is longer than the 2 hour limit."

    return result
