"""Tests for deterministic two-round full-text DeepSeek auditing."""

import json
import unittest

from modules.ai_provider import AIProviderJSONError
from modules.full_text_auditor import FullTextAuditError, audit_paragraphs


class ScriptedAuditProvider:
    def __init__(self, candidates_by_round=None, approve=True):
        self.candidates_by_round = list(candidates_by_round or [[], []])
        self.approve = approve
        self.audit_calls = 0

    def generate_json(self, prompt, content):
        if "FULL_TEXT_AUDIT_REVIEW" in prompt:
            records = json.loads(content)["candidates"]
            return json.dumps(
                {
                    "decisions": [
                        {
                            "id": item["id"],
                            "approved": self.approve,
                            "verified_replacement": item["replacement"] if self.approve else "",
                            "reason": "checked",
                        }
                        for item in records
                    ]
                },
                ensure_ascii=False,
            )
        self.audit_calls += 1
        index = min(self.audit_calls - 1, len(self.candidates_by_round) - 1)
        return json.dumps(
            {"candidates": self.candidates_by_round[index]}, ensure_ascii=False
        )


def _candidate(original="摩西", replacement="摩西", **overrides):
    value = {
        "paragraph_id": "P0001",
        "original": original,
        "replacement": replacement,
        "error_type": "ocr_error",
        "reason": "OCR错字",
        "confidence": 0.99,
    }
    value.update(overrides)
    return value


class FullTextAuditorTests(unittest.TestCase):
    def test_applies_only_independently_approved_unique_candidate(self):
        provider = ScriptedAuditProvider(
            [[_candidate("模西", "摩西")], []], approve=True
        )
        result = audit_paragraphs(["模西上山。", "百姓等候。"], provider)
        self.assertEqual(result["paragraphs"], ["摩西上山。", "百姓等候。"])
        self.assertEqual(result["full_audit_candidates"], 1)
        self.assertEqual(result["full_audit_applied"], 1)
        self.assertEqual(result["full_audit_rounds"], 2)

    def test_rejects_low_confidence_and_disallowed_rewrite(self):
        candidates = [
            _candidate("模西", "摩西", confidence=0.8),
            _candidate("上山", "登上高山", error_type="style_rewrite"),
        ]
        result = audit_paragraphs(["模西上山。"], ScriptedAuditProvider([candidates, []]))
        self.assertEqual(result["paragraphs"], ["模西上山。"])
        self.assertEqual(result["full_audit_applied"], 0)
        self.assertGreaterEqual(result["full_audit_rejected"], 2)

    def test_rejects_ambiguous_original_and_review_rejection(self):
        ambiguous = _candidate("摩西", "摩希")
        provider = ScriptedAuditProvider([[ambiguous], []], approve=False)
        result = audit_paragraphs(["摩西对摩西说。"], provider)
        self.assertEqual(result["paragraphs"], ["摩西对摩西说。"])
        self.assertEqual(result["full_audit_applied"], 0)

        provider = ScriptedAuditProvider(
            [[_candidate("模西", "摩西")], []], approve=False
        )
        result = audit_paragraphs(["模西上山。"], provider)
        self.assertEqual(result["paragraphs"], ["模西上山。"])
        self.assertEqual(result["full_audit_applied"], 0)

    def test_rejects_overlapping_approved_edits(self):
        candidates = [
            _candidate("模西上山", "摩西上山"),
            _candidate("上山", "上山去"),
        ]
        result = audit_paragraphs(["模西上山。"], ScriptedAuditProvider([candidates, []]))
        self.assertEqual(result["paragraphs"], ["摩西上山。"])
        self.assertEqual(result["full_audit_applied"], 1)
        self.assertGreaterEqual(result["full_audit_rejected"], 1)

    def test_invalid_json_shape_aborts(self):
        class InvalidProvider:
            def generate_json(self, prompt, content):
                _ = (prompt, content)
                return '{"approved": true}'

        with self.assertRaises(FullTextAuditError):
            audit_paragraphs(["正文。"], InvalidProvider())

    def test_known_fixed_phrase_is_still_independently_reviewed(self):
        result = audit_paragraphs(
            ["各位家人，主任请安。"], ScriptedAuditProvider([[], []], approve=True)
        )
        self.assertEqual(result["paragraphs"], ["各位家人，主内平安。"])
        self.assertEqual(result["full_audit_applied"], 1)

    def test_known_fixed_phrase_overrides_conflicting_model_replacement(self):
        model_candidate = _candidate(
            "逃暑假", "逃赎价", paragraph_id="P0001", confidence=0.99
        )
        result = audit_paragraphs(
            ["不能为住在逃城的人逃暑假。"],
            ScriptedAuditProvider([[model_candidate], []], approve=True),
        )
        self.assertEqual(result["paragraphs"], ["不能为住在逃城的人收赎价。"])

    def test_candidate_cannot_target_paragraph_outside_window(self):
        provider = ScriptedAuditProvider(
            [[_candidate("模西", "摩西", paragraph_id="P0002")], []]
        )
        result = audit_paragraphs(
            ["第一段很长。", "模西上山。"],
            provider,
            max_characters=15,
            overlap_characters=1,
        )
        self.assertEqual(result["paragraphs"], ["第一段很长。", "模西上山。"])

    def test_truncated_multi_paragraph_window_is_split_and_completed(self):
        class SizeLimitedProvider(ScriptedAuditProvider):
            def generate_json(self, prompt, content):
                if "FULL_TEXT_AUDIT_REVIEW" in prompt:
                    return super().generate_json(prompt, content)
                if len(content) > 1500:
                    raise AIProviderJSONError(
                        "truncated",
                        error_type="truncated",
                        finish_reason="length",
                    )
                return '{"candidates": []}'

        paragraphs = [(f"第{index}段。" + "文字" * 300) for index in range(4)]
        result = audit_paragraphs(paragraphs, SizeLimitedProvider())
        self.assertEqual(result["paragraphs"], paragraphs)
        self.assertTrue(
            any("响应过长" in warning and "自动拆分重试" in warning
                for warning in result["audit_warnings"])
        )
        self.assertTrue(any("共" in warning for warning in result["audit_warnings"]))

    def test_truncated_long_paragraph_uses_overlapping_slices_and_deduplicates(self):
        class LongParagraphProvider(ScriptedAuditProvider):
            def generate_json(self, prompt, content):
                if "FULL_TEXT_AUDIT_REVIEW" in prompt:
                    return super().generate_json(prompt, content)
                if len(content) > 1200:
                    raise AIProviderJSONError(
                        "truncated",
                        error_type="truncated",
                        finish_reason="length",
                    )
                candidates = []
                if "模西" in content:
                    candidates.append(_candidate("模西", "摩西"))
                return json.dumps({"candidates": candidates}, ensure_ascii=False)

        paragraph = "甲" * 1299 + "模西" + "乙" * 1299
        result = audit_paragraphs([paragraph], LongParagraphProvider())
        self.assertEqual(result["paragraphs"][0].count("摩西"), 1)
        self.assertEqual(result["full_audit_applied"], 1)

    def test_invalid_json_at_minimum_slice_aborts(self):
        class AlwaysInvalidProvider:
            def generate_json(self, prompt, content):
                _ = (prompt, content)
                raise AIProviderJSONError("invalid", error_type="invalid_json")

        with self.assertRaises(FullTextAuditError):
            audit_paragraphs(["正文" * 400], AlwaysInvalidProvider())

    def test_transport_failure_is_not_split(self):
        class NetworkFailureProvider:
            def __init__(self):
                self.calls = 0

            def generate_json(self, prompt, content):
                _ = (prompt, content)
                self.calls += 1
                raise RuntimeError("network unavailable")

        provider = NetworkFailureProvider()
        with self.assertRaises(FullTextAuditError):
            audit_paragraphs(["正文" * 2000], provider)
        self.assertEqual(provider.calls, 1)


if __name__ == "__main__":
    unittest.main()
