"""Phase 4B tests for long text chunking and correction."""

import unittest

from modules.correction_engine import correct_long_text
from modules.text_chunker import chunk_text
from modules.text_merger import merge_chunks


class MockProvider:
    def generate(self, prompt, content):
        _ = prompt
        return f"[corrected]{content}"


class FailingProvider:
    def generate(self, prompt, content):
        _ = prompt
        if "失败" in content:
            raise RuntimeError("mock failure")
        return f"[ok]{content}"


class Phase4BLongTextTests(unittest.TestCase):
    def test_short_text_does_not_create_unnecessary_chunks(self):
        text = "短文本。"
        self.assertEqual(chunk_text(text, max_length=3000), [text])

    def test_long_text_creates_multiple_chunks(self):
        text = "第一句。" * 20
        chunks = chunk_text(text, max_length=20)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(merge_chunks(chunks), text)

    def test_paragraph_boundaries_are_preserved(self):
        text = "第一段内容。\n\n第二段内容。\n\n第三段内容。"
        chunks = chunk_text(text, max_length=8)
        self.assertEqual(merge_chunks(chunks), text)
        self.assertIn("\n\n", merge_chunks(chunks))

    def test_mock_provider_correction_works(self):
        result = correct_long_text("第一段。\n\n第二段。", MockProvider(), max_length=8)
        self.assertTrue(result["success"])
        self.assertEqual(result["chunks_processed"], 2)
        self.assertIn("[corrected]", result["corrected_text"])

    def test_failed_chunk_keeps_original_content(self):
        text = "第一段。\n\n这一段会失败。\n\n第三段。"
        result = correct_long_text(text, FailingProvider(), max_length=8)
        self.assertTrue(result["success"])
        self.assertIn("这一段会失败。", result["corrected_text"])
        self.assertEqual(
            result["warnings"],
            ["Chunk 2 correction failed, original text preserved"],
        )

    def test_merge_keeps_correct_order(self):
        chunks = ["第一", "第二", "第三"]
        self.assertEqual(merge_chunks(chunks), "第一第二第三")


if __name__ == "__main__":
    unittest.main()

