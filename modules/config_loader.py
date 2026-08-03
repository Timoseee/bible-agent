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

    return {
        "env_path": ENV_PATH,
        "openai_api_key": openai_api_key,
        "deepseek_api_key": deepseek_api_key,
        "ai_provider": ai_provider,
        "vision_provider": vision_provider,
        "openai_api_key_configured": bool(openai_api_key),
        "deepseek_api_key_configured": bool(deepseek_api_key),
    }
