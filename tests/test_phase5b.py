"""Phase 5B tests for Bible checker integration into correction workflow."""

import json
import unittest

from modules.bible_checker import check_bible_terms, load_bible_database
from modules.bible_context_builder import build_bible_context
from modules.correction_engine import correct_with_bible_check


class BibleContextMockProvider:
    def __init__(self):
        self.correction_content = ""

    def generate(self, prompt, content):
        if "Return JSON only" in prompt:
            return json.dumps({"approved": True, "issues": [], "summary": "Approved."})

        self.correction_content = content
        if "创世记" in content:
            return "创世记中摩西带领以色列民出埃及。"
        return content.replace("Original text:\n", "").split("\n\n", 1)[0]


class RejectingReviewProvider:
    def generate(self, prompt, content):
        if "Return JSON only" in prompt:
            return json.dumps(
                {
                    "approved": False,
                    "issues": [{"type": "content_changed", "original": "", "corrected": "", "reason": ""}],
                    "summary": "Rejected.",
                }
            )
        return "创世记中摩西带领以色列民出埃及。"


class NoIssueMockProvider:
    def __init__(self):
        self.correction_content = ""

    def generate(self, prompt, content):
        if "Return JSON only" in prompt:
            return json.dumps({"approved": True, "issues": [], "summary": "Approved."})

        self.correction_content = content
        return "摩西带领百姓出埃及。"


class Phase5BBibleIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = load_bible_database()

    def test_bible_issue_is_detected_and_passed_to_context(self):
        result = check_bible_terms("创世纪", self.database)
        context = build_bible_context(result["issues"])
        self.assertIn("创世纪", context)
        self.assertIn("创世记", context)

    def test_normal_bible_terms_do_not_create_issues(self):
        result = check_bible_terms("摩西带领百姓出埃及。", self.database)
        self.assertEqual(result["issues"], [])

    def test_mock_provider_receives_bible_context(self):
        provider = BibleContextMockProvider()
        result = correct_with_bible_check("创世纪中摩西带领以色列民出埃及。", provider)
        self.assertTrue(result["approved"])
        self.assertIn("创世纪", provider.correction_content)
        self.assertIn("创世记", provider.correction_content)
        self.assertEqual(result["final_text"], "创世记中摩西带领以色列民出埃及。")

    def test_review_rejection_returns_original_text(self):
        original = "创世纪中摩西带领以色列民出埃及。"
        result = correct_with_bible_check(original, RejectingReviewProvider())
        self.assertFalse(result["approved"])
        self.assertEqual(result["final_text"], original)

    def test_no_bible_issue_means_normal_correction_workflow_continues(self):
        provider = NoIssueMockProvider()
        result = correct_with_bible_check("摩西带领百姓出埃及。", provider)
        self.assertTrue(result["approved"])
        self.assertIn("No possible Bible terminology issues detected.", provider.correction_content)
        self.assertEqual(result["final_text"], "摩西带领百姓出埃及。")


if __name__ == "__main__":
    unittest.main()
