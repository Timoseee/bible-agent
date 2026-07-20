"""Phase 4A tests for the basic correction engine."""

import unittest

from modules.correction_engine import correct_text, load_correction_prompt


class MockProvider:
    def generate(self, prompt, content):
        self.prompt = prompt
        self.content = content
        return "corrected result"


class Phase4ACorrectionEngineTests(unittest.TestCase):
    def test_correction_engine_can_load_prompt(self):
        prompt = load_correction_prompt()
        self.assertIn("professional Chinese Bible sermon proofreading assistant", prompt)
        self.assertIn("Return only the corrected text", prompt)

    def test_missing_provider_handling(self):
        result = correct_text("original text", None)
        self.assertFalse(result["success"])
        self.assertEqual(result["corrected_text"], "")
        self.assertIn("provider", result["error"])

    def test_mock_provider_response(self):
        provider = MockProvider()
        result = correct_text("original text", provider)
        self.assertTrue(result["success"])
        self.assertEqual(result["corrected_text"], "corrected result")
        self.assertEqual(provider.content, "original text")
        self.assertIn("Strict rules", provider.prompt)

    def test_output_format(self):
        result = correct_text("original text", MockProvider())
        self.assertIn("corrected_text", result)
        self.assertIn("success", result)
        self.assertIsInstance(result["corrected_text"], str)
        self.assertIs(result["success"], True)


if __name__ == "__main__":
    unittest.main()
