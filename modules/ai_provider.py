"""AI provider interface and provider selection helpers."""

from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """Raised when an AI provider cannot be configured or used."""


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


def create_ai_provider(config):
    """Create the configured AI provider without sending API requests."""
    provider_name = config.get("ai_provider", "deepseek")

    if provider_name == "deepseek":
        from modules.deepseek_provider import DeepSeekProvider

        return DeepSeekProvider(api_key=config.get("deepseek_api_key", ""))

    if provider_name == "openai":
        from modules.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=config.get("openai_api_key", ""))

    raise AIProviderError(f"Unsupported AI provider: {provider_name}")
