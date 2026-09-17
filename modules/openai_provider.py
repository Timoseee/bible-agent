"""OpenAI text and vision provider implementation."""

import base64
import mimetypes
from pathlib import Path

from openai import OpenAIError

from modules.ai_provider import AIProvider, AIProviderError, VisionAIProvider
from modules.network_client import create_openai_client, describe_api_error


class OpenAIProvider(AIProvider, VisionAIProvider):
    """OpenAI Responses API provider for text generation and image reading."""

    provider_name = "openai"
    text_model = "gpt-4o-mini"
    vision_model = "gpt-4o-mini"

    def __init__(self, api_key, proxy=""):
        if not api_key:
            raise AIProviderError("OPENAI_API_KEY is not configured in .env.")

        self.api_key = api_key
        self.client = create_openai_client(api_key, proxy=proxy)

    def generate(self, prompt, content):
        """Generate text through the OpenAI Responses API."""
        try:
            response = self.client.responses.create(
                model=self.text_model,
                instructions=prompt,
                input=content,
            )
        except OpenAIError as error:
            raise AIProviderError(describe_api_error("OpenAI", error)) from error

        return response.output_text

    def generate_from_image(self, prompt, image_path):
        """Read an image using a base64 data URL and return text."""
        path = Path(image_path)
        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"

        try:
            image_data = base64.b64encode(path.read_bytes()).decode("ascii")
            response = self.client.responses.create(
                model=self.vision_model,
                instructions=prompt,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "Process this image exactly as instructed."},
                            {
                                "type": "input_image",
                                "image_url": f"data:{mime_type};base64,{image_data}",
                                "detail": "high",
                            },
                        ],
                    }
                ],
            )
        except OpenAIError as error:
            raise AIProviderError(describe_api_error("OpenAI", error)) from error
        except OSError as error:
            raise AIProviderError(f"Image file could not be read: {error}") from error

        return response.output_text
