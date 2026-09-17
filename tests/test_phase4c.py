"""Phase 4C tests for review agent and preservation validator."""

import json
import unittest

from modules.ai_provider import AIProviderJSONError
from modules.correction_engine import correct_and_review
from modules.correction_validator import validate_preservation
from modules.review_agent import review_correction


class MockReviewProvider:
    def generate(self, prompt, content):
        _ = prompt
        if "浠ヨ壊鍒楀悕" in content and "浠ヨ壊鍒楁皯" in content:
            return json.dumps({"approved": True, "issues": [], "summary": "Valid correction."})

        if "鎽╄タ闈炲父鏁" in content:
            return json.dumps(
                {
                    "approved": False,
                    "issues": [
                        {
                            "type": "content_changed",
                            "original": "鎽╄タ涓婂北",
                            "corrected": "鎽╄タ闈炲父鏁檾鍦颁笂灞卞苟瀹屾垚浣垮懡",
                            "reason": "Corrected text adds new information and rewrites style.",
                        }
                    ],
                    "summary": "Content was changed.",
                }
            )

        return json.dumps({"approved": True, "issues": [], "summary": "Approved."})


class MockCorrectionAndReviewProvider:
    def generate(self, prompt, content):
        if "Return JSON only" in prompt:
            return json.dumps({"approved": True, "issues": [], "summary": "Approved."})
        return "浠ヨ壊鍒楁皯"


class FailingReviewProvider:
    def generate(self, prompt, content):
        if "Return JSON only" in prompt:
            raise RuntimeError("review failed")
        return "corrected text"


class FencedJSONReviewProvider:
    def generate(self, prompt, content):
        return self.generate_json(prompt, content)

    def generate_json(self, prompt, content):
        _ = (prompt, content)
        return 'Result:\n```json\n{"approved": true, "issues": [], "summary": "OK"}\n```'


class TruncatedThenCompactReviewProvider:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt, content):
        return self.generate_json(prompt, content)

    def generate_json(self, prompt, content):
        _ = content
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            raise AIProviderJSONError(
                "truncated",
                error_type="truncated",
                finish_reason="length",
            )
        return '{"approved":true,"issues":[],"summary":"通过"}'


class Phase4CReviewValidatorTests(unittest.TestCase):
    def test_review_approves_valid_correction(self):
        review = review_correction("浠ヨ壊鍒楀悕", "浠ヨ壊鍒楁皯", MockReviewProvider())
        self.assertTrue(review["approved"])
        self.assertEqual(review["issues"], [])

    def test_review_rejects_content_rewrite(self):
        review = review_correction(
            "鎽╄タ涓婂北",
            "鎽╄タ闈炲父鏁檾鍦颁笂灞卞苟瀹屾垚浣垮懡",
            MockReviewProvider(),
        )
        self.assertFalse(review["approved"])
        self.assertEqual(review["issues"][0]["type"], "content_changed")

    def test_review_accepts_json_inside_code_fence_and_extra_text(self):
        review = review_correction("原文", "原文", FencedJSONReviewProvider())
        self.assertTrue(review["approved"])

    def test_truncated_review_retries_with_minimal_json_instruction(self):
        provider = TruncatedThenCompactReviewProvider()
        review = review_correction("原文", "原文", provider)
        self.assertTrue(review["approved"])
        self.assertEqual(len(provider.prompts), 2)
        self.assertIn("minimal decision only", provider.prompts[1])

    def test_validator_detects_large_deletion(self):
        result = validate_preservation("一" * 10000, "一" * 5000)
        self.assertFalse(result["valid"])
        self.assertIn("Large text reduction detected", result["warnings"])

    def test_failed_review_returns_original_text(self):
        result = correct_and_review("original sermon text", FailingReviewProvider())
        self.assertFalse(result["approved"])
        self.assertEqual(result["final_text"], "original sermon text")
        self.assertIn("Review failed, original text preserved", result["warnings"])

    def test_mock_provider_works_without_api_key(self):
        result = correct_and_review("浠ヨ壊鍒楀悕", MockCorrectionAndReviewProvider())
        self.assertTrue(result["approved"])
        self.assertEqual(result["final_text"], "浠ヨ壊鍒楁皯")


if __name__ == "__main__":
    unittest.main()
