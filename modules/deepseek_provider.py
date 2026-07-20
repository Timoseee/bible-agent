"""DeepSeek provider implementation for AI text generation."""

from openai import OpenAI, OpenAIError

from modules.ai_provider import AIProvider, AIProviderError


class DeepSeekProvider(AIProvider):
    """DeepSeek API provider following the AIProvider interface."""

    provider_name = "deepseek"
    base_url = "https://api.deepseek.com"
    model = "deepseek-chat"

    def __init__(self, api_key):
        if not api_key:
            raise AIProviderError("DEEPSEEK_API_KEY is not configured in .env.")

        self.api_key = api_key
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

    def generate(self, prompt, content):
        """Send prompt and content to DeepSeek and return response text."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": content},
                ],
                temperature=0,
            )
        except OpenAIError as error:
            raise AIProviderError(f"DeepSeek API request failed: {error}") from error

        return response.choices[0].message.content
