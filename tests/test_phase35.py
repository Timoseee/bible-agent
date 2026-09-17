"""Phase 3.5 tests for AI provider abstraction."""

import os
import unittest
import shutil
import httpx
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openai import APIConnectionError

from modules.ai_provider import AIProviderError, AIProviderJSONError, create_ai_provider
from modules.config_loader import load_config
from modules.deepseek_provider import DeepSeekProvider
from modules.openai_provider import OpenAIProvider


class Phase35AIProviderTests(unittest.TestCase):
    def test_configuration_loading(self):
        env = {
            "OPENAI_API_KEY": "openai-test",
            "DEEPSEEK_API_KEY": "deepseek-test",
            "AI_PROVIDER": "deepseek",
        }
        with patch.dict(os.environ, env, clear=False):
            config = load_config()

        self.assertEqual(config["openai_api_key"], "openai-test")
        self.assertEqual(config["deepseek_api_key"], "deepseek-test")
        self.assertEqual(config["ai_provider"], "deepseek")

    def test_deepseek_provider_selection(self):
        config = {"ai_provider": "deepseek", "deepseek_api_key": "test-key"}
        provider = create_ai_provider(config)
        self.assertIsInstance(provider, DeepSeekProvider)

    def test_openai_provider_selection(self):
        config = {"ai_provider": "openai", "openai_api_key": "test-key"}
        provider = create_ai_provider(config)
        self.assertIsInstance(provider, OpenAIProvider)

    def test_deepseek_provider_initialization(self):
        provider = DeepSeekProvider(api_key="test-key")
        self.assertEqual(provider.provider_name, "deepseek")
        self.assertEqual(provider.model, "deepseek-v4-flash")

    def test_deepseek_json_generation_uses_v4_and_json_mode(self):
        provider = DeepSeekProvider(api_key="test-key")
        provider.client.chat.completions.create = Mock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
            )
        )
        result = provider.generate_json("Return JSON", "content")
        self.assertEqual(result, '{"ok": true}')
        request = provider.client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["model"], "deepseek-v4-flash")
        self.assertEqual(request["response_format"], {"type": "json_object"})
        self.assertEqual(request["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(request["max_tokens"], 8192)

    def test_deepseek_json_retries_empty_response(self):
        provider = DeepSeekProvider(api_key="test-key", max_retries=3)
        provider.client.chat.completions.create = Mock(
            side_effect=[
                SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=""))]
                ),
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content='```json\n{"approved": true}\n```'
                            )
                        )
                    ]
                ),
            ]
        )
        self.assertEqual(
            provider.generate_json("Return JSON", "content"),
            '{"approved": true}',
        )
        self.assertEqual(provider.client.chat.completions.create.call_count, 2)

    def test_deepseek_json_reports_length_truncation_without_blind_retry(self):
        provider = DeepSeekProvider(api_key="test-key", max_retries=3)
        provider.client.chat.completions.create = Mock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="length",
                        message=SimpleNamespace(content='{"candidates":[{"reason":"未完成'),
                    )
                ]
            )
        )
        with self.assertRaises(AIProviderJSONError) as raised:
            provider.generate_json("Return JSON", "content")
        self.assertEqual(raised.exception.error_type, "truncated")
        self.assertEqual(raised.exception.finish_reason, "length")
        self.assertEqual(provider.client.chat.completions.create.call_count, 1)

    def test_deepseek_json_retries_malformed_then_accepts_valid_response(self):
        provider = DeepSeekProvider(api_key="test-key", max_retries=3)
        provider.client.chat.completions.create = Mock(
            side_effect=[
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            finish_reason="stop",
                            message=SimpleNamespace(content='{"ok": truX}'),
                        )
                    ]
                ),
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            finish_reason="stop",
                            message=SimpleNamespace(content='{"ok": true}'),
                        )
                    ]
                ),
            ]
        )
        self.assertEqual(provider.generate_json("Return JSON", "content"), '{"ok": true}')
        self.assertEqual(provider.client.chat.completions.create.call_count, 2)

    def test_deepseek_text_rebuilds_client_after_connection_error(self):
        provider = DeepSeekProvider(api_key="test-key", max_retries=3)
        connection_error = APIConnectionError(
            request=httpx.Request("POST", "https://api.deepseek.com/chat/completions")
        )
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="corrected"))]
        )
        provider._create_completion = Mock(side_effect=[connection_error, response])
        provider._reset_client = Mock()
        with patch("modules.deepseek_provider.time.sleep"):
            self.assertEqual(provider.generate("prompt", "content"), "corrected")
        provider._reset_client.assert_called_once()

    def test_openai_provider_initialization(self):
        provider = OpenAIProvider(api_key="test-key")
        self.assertEqual(provider.provider_name, "openai")

    def test_openai_text_generation_uses_responses_api(self):
        provider = OpenAIProvider(api_key="test-key")
        provider.client.responses.create = Mock(
            return_value=SimpleNamespace(output_text="corrected")
        )

        self.assertEqual(provider.generate("instructions", "content"), "corrected")
        provider.client.responses.create.assert_called_once_with(
            model="gpt-4o-mini",
            instructions="instructions",
            input="content",
        )

    def test_openai_vision_generation_sends_image_data_url(self):
        provider = OpenAIProvider(api_key="test-key")
        provider.client.responses.create = Mock(
            return_value=SimpleNamespace(output_text="image text")
        )

        folder = Path(__file__).resolve().parent / "tmp_phase35"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            image_path = folder / "page.png"
            image_path.write_bytes(b"image-bytes")
            result = provider.generate_from_image("read", image_path)
        finally:
            shutil.rmtree(folder, ignore_errors=True)

        self.assertEqual(result, "image text")
        request = provider.client.responses.create.call_args.kwargs
        image_input = request["input"][0]["content"][1]
        self.assertTrue(image_input["image_url"].startswith("data:image/png;base64,"))

    def test_missing_api_key_handling(self):
        with self.assertRaises(AIProviderError):
            DeepSeekProvider(api_key="")

        with self.assertRaises(AIProviderError):
            OpenAIProvider(api_key="")

    def test_unknown_provider_handling(self):
        config = {"ai_provider": "unknown"}
        with self.assertRaises(AIProviderError):
            create_ai_provider(config)


if __name__ == "__main__":
    unittest.main()
