"""AI provider interface and provider selection helpers."""

from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """Raised when an AI provider cannot be configured or used."""


class AIProviderJSONError(AIProviderError):
    """Raised when a provider response cannot be decoded as complete JSON."""

    def __init__(self, message, *, error_type="invalid_json", finish_reason="", preview=""):
        super().__init__(message)
        self.error_type = str(error_type or "invalid_json")
        self.finish_reason = str(finish_reason or "")
        self.preview = str(preview or "")


class AIProvider(ABC):
    """Standard interface for future AI model providers."""

    @abstractmethod
    def generate(self, prompt, content):
        """Generate text from a prompt and content."""
        raise NotImplementedError


class VisionAIProvider(ABC):
    """Interface extension for providers that can read images."""

    @abstractmethod
    def generate_from_image(self, prompt, image_path):
        """Generate text from a prompt and an image path."""
        raise NotImplementedError


def create_ai_provider(config, provider_name=None):
    """Create the configured AI provider without sending API requests."""
    provider_name = (provider_name or config.get("ai_provider", "deepseek")).strip().lower()

    if provider_name == "deepseek":
        from modules.deepseek_provider import DeepSeekProvider

        return DeepSeekProvider(
            api_key=config.get("deepseek_api_key", ""),
            proxy=config.get("api_proxy", ""),
            model=config.get("deepseek_model", "deepseek-v4-flash"),
            timeout=config.get("api_timeout_seconds", 600.0),
            max_retries=config.get("api_max_retries", 3),
        )

    if provider_name == "openai":
        from modules.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=config.get("openai_api_key", ""),
            proxy=config.get("api_proxy", ""),
        )

    raise AIProviderError(f"Unsupported AI provider: {provider_name}")
