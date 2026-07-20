"""Phase 3.5 tests for AI provider abstraction."""

import os
import unittest
from unittest.mock import patch

from modules.ai_provider import AIProviderError, create_ai_provider
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

    def test_openai_provider_initialization(self):
        provider = OpenAIProvider(api_key="test-key")
        self.assertEqual(provider.provider_name, "openai")

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
