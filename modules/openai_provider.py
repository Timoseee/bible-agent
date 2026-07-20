"""OpenAI provider framework for future AI tasks."""

from modules.ai_provider import AIProvider, AIProviderError


class OpenAIProvider(AIProvider):
    """Connection framework for future OpenAI model integration."""

    provider_name = "openai"

    def __init__(self, api_key):
        if not api_key:
            raise AIProviderError("OPENAI_API_KEY is not configured in .env.")

        self.api_key = api_key

    def generate(self, prompt, content):
        """Prepare the future OpenAI generation call."""
        _ = (prompt, content)
        raise NotImplementedError("OpenAI generation will be implemented in a future phase.")
