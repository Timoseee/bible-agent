"""Raw audio transcription with OpenAI Whisper."""

import tempfile
from pathlib import Path

from openai import OpenAI

from modules.audio_processor import MAX_DURATION_MINUTES, analyze_audio
from modules.config_loader import load_config


SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".m4a"}
MAX_DIRECT_UPLOAD_MB = 24
CHUNK_LENGTH_MINUTES = 20


class AudioTranscriptionError(Exception):
    """Raised when raw audio transcription cannot be completed."""


def _validate_audio_path(audio_path):
    path = Path(audio_path)

    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    if not path.is_file():
        raise AudioTranscriptionError(f"Audio path is not a file: {path}")

    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise AudioTranscriptionError("Only .mp3 and .m4a audio files are supported.")

    return path


def _transcribe_file(client, file_path):
    with Path(file_path).open("rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="zh",
        )

    return getattr(transcription, "text", "")


def _split_audio_to_temp_files(audio_path, temp_dir):
    try:
        from pydub import AudioSegment
    except ImportError as error:
        raise AudioTranscriptionError("pydub is required to split long audio files.") from error

    try:
        audio = AudioSegment.from_file(audio_path)
    except Exception as error:
        raise AudioTranscriptionError(
            "Audio splitting failed. Install ffmpeg if this file must be split."
        ) from error

    chunk_length_ms = CHUNK_LENGTH_MINUTES * 60 * 1000
    extension = Path(audio_path).suffix.lower().lstrip(".")
    chunk_paths = []

    for index, start_ms in enumerate(range(0, len(audio), chunk_length_ms), start=1):
        chunk = audio[start_ms : start_ms + chunk_length_ms]
        chunk_path = Path(temp_dir) / f"chunk_{index:03d}.{extension}"
        chunk.export(chunk_path, format=extension)
        chunk_paths.append(chunk_path)

    return chunk_paths


def transcribe_audio(audio_path):
    """Convert an MP3/M4A audio file into raw Chinese text.

    This function performs raw transcription only. It does not correct,
    summarize, format, check Bible references, or save transcript files.
    """
    path = _validate_audio_path(audio_path)
    config = load_config()

    if not config["openai_api_key"]:
        raise AudioTranscriptionError("OPENAI_API_KEY is not configured in .env.")

    audio_info = analyze_audio(path)

    if audio_info["duration_minutes"] is None:
        raise AudioTranscriptionError(audio_info["warning"] or "Audio duration could not be verified.")

    if audio_info["duration_minutes"] > MAX_DURATION_MINUTES:
        raise AudioTranscriptionError("Audio is longer than the 2 hour maximum supported duration.")

    client = OpenAI(api_key=config["openai_api_key"], timeout=600.0)
    text_parts = []

    if audio_info["size_mb"] <= MAX_DIRECT_UPLOAD_MB:
        text_parts.append(_transcribe_file(client, path))
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            chunk_paths = _split_audio_to_temp_files(path, temp_dir)
            for chunk_path in chunk_paths:
                text_parts.append(_transcribe_file(client, chunk_path))

    merged_text = "\n".join(part.strip() for part in text_parts if part and part.strip())

    return {
        "filename": path.name,
        "language": "zh",
        "text": merged_text,
    }
