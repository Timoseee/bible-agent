"""Phase 7C tests for image DOCX template analysis and style mapping."""

import hashlib
import json
import unittest
from pathlib import Path

from modules.image_docx_analyzer import analyze_image_template
from modules.image_docx_renderer import prepare_image_document
from modules.style_mapper import build_style_mapping, save_style_mapping
from modules.template_manager import load_template


BASE_DIR = Path(__file__).resolve().parent.parent
IMAGE_TEMPLATE = BASE_DIR / "templates" / "image_template.docx"
STYLE_DATABASE = BASE_DIR / "database" / "docx_styles.json"


def _file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Phase7CImageDocxFoundationTests(unittest.TestCase):
    def test_image_template_loads(self):
        template = load_template("image")
        self.assertFalse(isinstance(template, str))

    def test_analyzer_detects_colors(self):
        analysis = analyze_image_template(IMAGE_TEMPLATE)
        self.assertGreater(len(analysis["colors"]), 0)

    def test_analyzer_detects_multiple_styles(self):
        analysis = analyze_image_template(IMAGE_TEMPLATE)
        self.assertGreaterEqual(len(analysis["styles"]), 2)

    def test_style_mapping_generation_works(self):
        mapping = build_style_mapping(IMAGE_TEMPLATE)
        self.assertIn("title_style", mapping)
        self.assertIn("body_style", mapping)
        self.assertIn("colors", mapping)

    def test_original_template_is_unchanged(self):
        before = _file_hash(IMAGE_TEMPLATE)
        mapping = build_style_mapping(IMAGE_TEMPLATE)
        prepare_image_document("测试文本", mapping, IMAGE_TEMPLATE)
        after = _file_hash(IMAGE_TEMPLATE)
        self.assertEqual(before, after)

    def test_style_database_saves_correctly(self):
        mapping = build_style_mapping(IMAGE_TEMPLATE)
        save_style_mapping("image_template", mapping, STYLE_DATABASE)
        database = json.loads(STYLE_DATABASE.read_text(encoding="utf-8-sig"))
        self.assertIn("image_template", database)
        self.assertIn("styles", database["image_template"])
        self.assertIn("colors", database["image_template"])


if __name__ == "__main__":
    unittest.main()
