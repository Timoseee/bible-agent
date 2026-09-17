"""Configuration loading for the BibleAI project."""

import os
from dotenv import load_dotenv
from modules.resource_path import resource_path, writable_path


ENV_PATH = writable_path(".env") if writable_path(".env").exists() else resource_path(".env")


def load_config():
    """Load environment configuration and return known settings."""
    global ENV_PATH
    user_env_path = writable_path(".env")
    ENV_PATH = user_env_path if user_env_path.exists() else resource_path(".env")
    load_dotenv(ENV_PATH, encoding="utf-8-sig")
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
    ai_provider = os.getenv("AI_PROVIDER", "deepseek").strip().lower() or "deepseek"
    vision_provider = os.getenv("VISION_PROVIDER", ai_provider).strip().lower() or ai_provider
    audio_transcription_provider = (
        os.getenv("AUDIO_TRANSCRIPTION_PROVIDER", "openai").strip().lower() or "openai"
    )
    local_whisper_model = os.getenv("LOCAL_WHISPER_MODEL", "small").strip() or "small"
    local_whisper_device = os.getenv("LOCAL_WHISPER_DEVICE", "cpu").strip() or "cpu"
    local_whisper_compute_type = (
        os.getenv("LOCAL_WHISPER_COMPUTE_TYPE", "int8").strip() or "int8"
    )
    api_proxy = os.getenv("API_PROXY", "").strip()
    local_ocr_provider = os.getenv("LOCAL_OCR_PROVIDER", "rapidocr").strip().lower() or "rapidocr"
    deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash"

    def _integer(name, default, minimum=1):
        try:
            return max(minimum, int(os.getenv(name, str(default))))
        except ValueError:
            return default

    def _number(name, default, minimum=0.0, maximum=None):
        try:
            value = max(minimum, float(os.getenv(name, str(default))))
            return min(value, maximum) if maximum is not None else value
        except ValueError:
            return default

    api_timeout_seconds = _number("DEEPSEEK_API_TIMEOUT_SECONDS", 600.0, minimum=1.0)
    api_max_retries = _integer("DEEPSEEK_API_MAX_RETRIES", 3)
    ocr_min_characters = _integer("OCR_MIN_CHARACTERS_PER_PAGE", 5)
    ocr_min_confidence = _number("OCR_MIN_AVERAGE_CONFIDENCE", 0.55, maximum=1.0)
    full_audit_min_confidence = _number(
        "FULL_AUDIT_MIN_CONFIDENCE", 0.92, maximum=1.0
    )
    full_audit_window_characters = _integer("FULL_AUDIT_WINDOW_CHARACTERS", 6000)
    full_audit_overlap_characters = _integer("FULL_AUDIT_OVERLAP_CHARACTERS", 600)

    return {
        "env_path": ENV_PATH,
        "openai_api_key": openai_api_key,
        "deepseek_api_key": deepseek_api_key,
        "ai_provider": ai_provider,
        "vision_provider": vision_provider,
        "audio_transcription_provider": audio_transcription_provider,
        "local_whisper_model": local_whisper_model,
        "local_whisper_device": local_whisper_device,
        "local_whisper_compute_type": local_whisper_compute_type,
        "api_proxy": api_proxy,
        "local_ocr_provider": local_ocr_provider,
        "deepseek_model": deepseek_model,
        "api_timeout_seconds": api_timeout_seconds,
        "api_max_retries": api_max_retries,
        "ocr_min_characters": ocr_min_characters,
        "ocr_min_confidence": ocr_min_confidence,
        "full_audit_min_confidence": full_audit_min_confidence,
        "full_audit_window_characters": full_audit_window_characters,
        "full_audit_overlap_characters": full_audit_overlap_characters,
        "openai_api_key_configured": bool(openai_api_key),
        "deepseek_api_key_configured": bool(deepseek_api_key),
    }
