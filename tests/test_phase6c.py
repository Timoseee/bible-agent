"""Phase 6C tests for watermark detection and OCR text cleaning."""

import unittest

from modules.text_cleaning_pipeline import clean_ocr_text
from modules.watermark_detector import clean_watermarks, detect_watermarks, load_watermark_database


class Phase6CWatermarkCleaningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = load_watermark_database()

    def test_known_watermark_detected(self):
        result = detect_watermarks("神与以色列民立约\n\n来自小米笔记", self.database)
        self.assertTrue(result["found"])
        self.assertEqual(result["watermarks"][0]["text"], "来自小米笔记")

    def test_watermark_removed_correctly(self):
        detection = detect_watermarks("神与以色列民立约\n\n来自小米笔记", self.database)
        cleaned = clean_watermarks("神与以色列民立约\n\n来自小米笔记", detection["watermarks"])
        self.assertEqual(cleaned, "神与以色列民立约")

    def test_normal_sermon_text_preserved(self):
        text = "小米是一种植物，不是水印。"
        result = clean_ocr_text(text)
        self.assertEqual(result["cleaned_text"], text)
        self.assertEqual(result["removed_watermarks"], [])

    def test_unknown_words_not_removed(self):
        text = "这是普通讲章内容，包含未知词语。"
        result = clean_ocr_text(text)
        self.assertEqual(result["cleaned_text"], text)

    def test_empty_text_handled(self):
        result = clean_ocr_text("")
        self.assertEqual(result["cleaned_text"], "")
        self.assertEqual(result["removed_watermarks"], [])

    def test_multiple_watermarks_handled(self):
        text = "讲章内容\nCamScanner\n扫描全能王"
        result = clean_ocr_text(text)
        self.assertEqual(result["cleaned_text"], "讲章内容")
        removed = [item["text"] for item in result["removed_watermarks"]]
        self.assertIn("CamScanner", removed)
        self.assertIn("扫描全能王", removed)


if __name__ == "__main__":
    unittest.main()
