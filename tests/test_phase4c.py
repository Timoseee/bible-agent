"""Phase 4C tests for review agent and preservation validator."""

import json
import unittest

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
