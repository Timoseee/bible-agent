"""Phase 7A tests for DOCX template analysis and generation foundation."""

import hashlib
import unittest
from pathlib import Path

from docx import Document

from modules.docx_analyzer import analyze_template
from modules.docx_generator import generate_docx
from modules.template_manager import get_template_info


BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_TEMPLATE = BASE_DIR / "templates" / "audio_template.docx"
IMAGE_TEMPLATE = BASE_DIR / "templates" / "image_template.docx"
TEST_OUTPUT = BASE_DIR / "output" / "docx" / "phase7a_test.docx"


def _file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Phase7ADocxFoundationTests(unittest.TestCase):
    def tearDown(self):
        if TEST_OUTPUT.exists():
            TEST_OUTPUT.unlink()

    def test_audio_template_analysis_works(self):
        info = analyze_template(AUDIO_TEMPLATE)
        self.assertEqual(info["filename"], "audio_template.docx")
        self.assertGreaterEqual(info["paragraph_count"], 0)
        self.assertGreater(info["style_count"], 0)

    def test_image_template_analysis_works(self):
        info = analyze_template(IMAGE_TEMPLATE)
        self.assertEqual(info["filename"], "image_template.docx")
        self.assertGreaterEqual(info["paragraph_count"], 0)
        self.assertGreater(info["style_count"], 0)

    def test_template_information_contains_styles(self):
        info = get_template_info("audio")
        self.assertTrue(info["success"])
        self.assertIn("styles", info)
        self.assertGreater(len(info["styles"]), 0)

    def test_generated_docx_opens_successfully(self):
        result = generate_docx("第一段测试。\n\n第二段测试。", AUDIO_TEMPLATE, TEST_OUTPUT)
        self.assertTrue(result["success"])
        self.assertTrue(TEST_OUTPUT.exists())
        document = Document(TEST_OUTPUT)
        self.assertGreaterEqual(len(document.paragraphs), 2)

    def test_original_templates_are_unchanged(self):
        before = _file_hash(AUDIO_TEMPLATE)
        generate_docx("测试文本。", AUDIO_TEMPLATE, TEST_OUTPUT)
        after = _file_hash(AUDIO_TEMPLATE)
        self.assertEqual(before, after)

    def test_missing_template_error_handling(self):
        missing = BASE_DIR / "templates" / "missing_template.docx"
        with self.assertRaises(FileNotFoundError):
            generate_docx("测试文本。", missing, TEST_OUTPUT)


if __name__ == "__main__":
    unittest.main()
