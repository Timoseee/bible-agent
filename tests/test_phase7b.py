"""Phase 7B tests for audio DOCX generation."""

import hashlib
import unittest
from pathlib import Path

from docx import Document

from modules.audio_docx_formatter import generate_audio_docx
from modules.paragraph_optimizer import (
    extract_audio_title,
    optimize_audio_paragraphs,
    structure_audio_paragraphs,
)
from modules.template_manager import load_template


BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_TEMPLATE = BASE_DIR / "templates" / "audio_template.docx"
TEST_OUTPUT = BASE_DIR / "output" / "docx" / "phase7b_audio_test.docx"


def _file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Phase7BAudioDocxTests(unittest.TestCase):
    def tearDown(self):
        if TEST_OUTPUT.exists():
            TEST_OUTPUT.unlink()

    def test_audio_template_loads(self):
        template = load_template("audio")
        self.assertFalse(isinstance(template, str))

    def test_text_generates_valid_docx(self):
        result = generate_audio_docx("第一句。第二句。", AUDIO_TEMPLATE, TEST_OUTPUT)
        self.assertTrue(result["success"])
        self.assertTrue(TEST_OUTPUT.exists())

    def test_generated_docx_can_reopen(self):
        generate_audio_docx("第一句。第二句。", AUDIO_TEMPLATE, TEST_OUTPUT)
        document = Document(TEST_OUTPUT)
        self.assertGreater(len(document.paragraphs), 0)

    def test_empty_paragraphs_removed(self):
        result = generate_audio_docx("第一句。\n\n\n\n第二句。", AUDIO_TEMPLATE, TEST_OUTPUT)
        self.assertEqual(result["paragraphs_inserted"], 1)

    def test_font_color_becomes_black(self):
        generate_audio_docx("黑色文字测试。", AUDIO_TEMPLATE, TEST_OUTPUT)
        document = Document(TEST_OUTPUT)
        inserted_runs = [
            run
            for paragraph in document.paragraphs
            for run in paragraph.runs
            if "黑色文字测试" in run.text
        ]
        self.assertTrue(inserted_runs)
        self.assertEqual(str(inserted_runs[0].font.color.rgb), "000000")

    def test_original_template_unchanged(self):
        before = _file_hash(AUDIO_TEMPLATE)
        generate_audio_docx("模板不应被修改。", AUDIO_TEMPLATE, TEST_OUTPUT)
        after = _file_hash(AUDIO_TEMPLATE)
        self.assertEqual(before, after)

    def test_template_sample_text_is_not_kept(self):
        template_document = Document(AUDIO_TEMPLATE)
        sample_title = template_document.paragraphs[0].text.strip()
        generate_audio_docx("这是新生成的正文内容。", AUDIO_TEMPLATE, TEST_OUTPUT)
        output_document = Document(TEST_OUTPUT)
        output_texts = [paragraph.text.strip() for paragraph in output_document.paragraphs if paragraph.text.strip()]
        self.assertNotIn(sample_title, output_texts)
        self.assertIn("这是新生成的正文内容。", output_texts)

    def test_body_format_matches_template(self):
        template_document = Document(AUDIO_TEMPLATE)
        template_body = template_document.paragraphs[1]
        generate_audio_docx("格式应与模板正文一致。", AUDIO_TEMPLATE, TEST_OUTPUT)
        output_document = Document(TEST_OUTPUT)
        output_paragraph = next(
            paragraph
            for paragraph in output_document.paragraphs
            if "格式应与模板正文一致" in paragraph.text
        )
        self.assertEqual(
            output_paragraph.paragraph_format.first_line_indent,
            template_body.paragraph_format.first_line_indent,
        )
        self.assertEqual(
            output_paragraph.paragraph_format.line_spacing,
            template_body.paragraph_format.line_spacing,
        )
        self.assertEqual(output_paragraph.runs[0].font.size, template_body.runs[0].font.size)
        self.assertEqual(output_paragraph.runs[0].font.name, template_body.runs[0].font.name)

    def test_paragraph_optimization_works(self):
        text = "第一句。\n第二句。\n第三句。\n第四句。"
        paragraphs = optimize_audio_paragraphs(text)
        self.assertEqual(paragraphs, ["第一句。第二句。第三句。第四句。"])

    def test_extracts_chapter_title(self):
        text = "各位亲爱的家人 主内平安 我们一同学习出埃及记的第十九章 这一章经文主要是"
        self.assertEqual(extract_audio_title(text), "出埃及记第十九章")

    def test_structures_title_and_body_paragraphs(self):
        text = (
            "各位亲爱的家人 主内平安 我们一同学习出埃及记的第十九章 "
            "这一章经文主要是起到承前启后的作用 那么第一节就说到百姓来到西奈旷野 "
            "然后神在山上呼唤摩西 接着百姓回应愿意遵行耶和华的话 "
            "最后我们看第三段经文记载上帝再召摩西并吩咐百姓自洁预备"
        )
        structured = structure_audio_paragraphs(text)
        self.assertEqual(structured[0]["role"], "title")
        self.assertEqual(structured[0]["text"], "出埃及记第十九章")
        self.assertGreaterEqual(len([item for item in structured if item["role"] == "body"]), 2)

    def test_generated_docx_has_title_format(self):
        template_document = Document(AUDIO_TEMPLATE)
        template_title = template_document.paragraphs[0]
        text = "各位亲爱的家人 我们一同学习出埃及记的第十九章 那么神呼唤摩西上山 然后百姓回应遵行"
        generate_audio_docx(text, AUDIO_TEMPLATE, TEST_OUTPUT)
        output_document = Document(TEST_OUTPUT)
        title_paragraph = output_document.paragraphs[0]
        self.assertEqual(title_paragraph.text, "出埃及记第十九章")
        self.assertEqual(title_paragraph.runs[0].font.size, template_title.runs[0].font.size)
        self.assertGreaterEqual(len([p for p in output_document.paragraphs if p.text.strip()]), 2)


if __name__ == "__main__":
    unittest.main()
