"""Tests for sermon editorial polish stage."""

import unittest
from pathlib import Path
from unittest.mock import Mock

from modules.polish_engine import load_polish_prompt, polish_sermon_text


BASE_DIR = Path(__file__).resolve().parent.parent
POLISH_PROMPT = BASE_DIR / "prompts" / "polish_prompt.txt"


class PolishEngineTests(unittest.TestCase):
    def test_polish_prompt_exists(self):
        self.assertTrue(POLISH_PROMPT.exists())
        prompt = load_polish_prompt()
        self.assertIn("punctuation", prompt)
        self.assertIn("paragraph", prompt)
        self.assertIn("啊", prompt)
        self.assertIn("one Bible verse unit = one paragraph", prompt)

    def test_polish_requires_provider(self):
        result = polish_sermon_text("测试文本。", None)
        self.assertFalse(result["success"])
        self.assertEqual(result["polished_text"], "测试文本。")

    def test_polish_calls_provider_and_merges(self):
        provider = Mock()
        provider.generate.side_effect = [
            "出埃及记第十九章\n\n各位亲爱的家人，主内平安。",
            "神在西奈山上呼唤摩西。",
        ]
        text = "各位亲爱的家人 主内平安。\n\n神在西奈山上呼唤摩西。"
        result = polish_sermon_text(text, provider, max_length=20)
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["chunks_processed"], 2)
        self.assertIn("出埃及记第十九章", result["polished_text"])
        self.assertIn("西奈山", result["polished_text"])
        self.assertIn("\n\n", result["polished_text"])

    def test_polish_preserves_original_when_output_too_short(self):
        provider = Mock()
        provider.generate.return_value = "太短"
        original = "这是一段足够长的讲道文本，用来测试润色结果过短时应当保留原文。" * 5
        result = polish_sermon_text(original, provider)
        self.assertFalse(result["success"])
        self.assertEqual(result["polished_text"], original)

    def test_failed_or_empty_chunk_is_not_success(self):
        original = "神呼唤摩西。\n\n摩西回应神。"
        for second_result in (RuntimeError("connection failed"), "", None):
            with self.subTest(second_result=second_result):
                provider = Mock()
                provider.generate.side_effect = ["神呼唤摩西。", second_result]
                result = polish_sermon_text(original, provider, max_length=10)
                self.assertFalse(result["success"])
                self.assertEqual(result["polished_text"], original)
                self.assertTrue(result["warnings"])


if __name__ == "__main__":
    unittest.main()
