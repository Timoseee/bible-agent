"""Tests for the one-click local-OCR image batch workflow."""

import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from modules.ai_provider import AIProviderJSONError
from modules.correction_engine import correct_image_text_strict
from modules.local_ocr_provider import RapidOCRProvider
from modules.pipeline_controller import _collect_image_paths, process_image_input
from modules.text_cleaning_pipeline import clean_image_ocr_text


TEST_DIR = Path(__file__).resolve().parent / "tmp_image_batch"


def _image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 40), color="white").save(path)


class PassThroughDeepSeek:
    provider_name = "deepseek"

    def generate(self, prompt, content):
        _ = prompt
        return content

    def generate_json(self, prompt, content):
        _ = (prompt, content)
        if "FULL_TEXT_AUDIT_REVIEW" in prompt:
            return '{"decisions": []}'
        if "FULL_TEXT_AUDIT" in prompt:
            return '{"candidates": []}'
        return '{"approved": true, "issues": [], "summary": "approved"}'


class RejectingDeepSeek(PassThroughDeepSeek):
    def generate_json(self, prompt, content):
        if "FULL_TEXT_AUDIT" in prompt:
            return super().generate_json(prompt, content)
        _ = (prompt, content)
        return '{"approved": false, "issues": [], "summary": "rejected"}'


class RevisingDeepSeek(PassThroughDeepSeek):
    def __init__(self):
        self.reviews = 0

    def generate(self, prompt, content):
        if "previous correction was rejected" in prompt:
            return content
        return content.replace("我的生活", "你的生活")

    def generate_json(self, prompt, content):
        _ = (prompt, content)
        self.reviews += 1
        if self.reviews == 1:
            return '{"approved": false, "issues": [], "summary": "pronoun changed"}'
        return '{"approved": true, "issues": [], "summary": "approved"}'


class ReformattingDeepSeek(PassThroughDeepSeek):
    def generate(self, prompt, content):
        _ = prompt
        return content.replace("\n", "")


class FailingAuditDeepSeek(PassThroughDeepSeek):
    def generate_json(self, prompt, content):
        if "FULL_TEXT_AUDIT" in prompt:
            raise RuntimeError("audit unavailable")
        return super().generate_json(prompt, content)


class InvalidMinimumAuditDeepSeek(PassThroughDeepSeek):
    def generate_json(self, prompt, content):
        if "FULL_TEXT_AUDIT" in prompt and "FULL_TEXT_AUDIT_REVIEW" not in prompt:
            raise AIProviderJSONError("invalid", error_type="invalid_json")
        return super().generate_json(prompt, content)


class PageOCR:
    def __init__(self, confidence=0.98, text="这是本页识别出来的中文内容。"):
        self.confidence = confidence
        self.text = text

    def extract_page(self, image_path):
        return {
            "filename": Path(image_path).name,
            "text": self.text,
            "confidence": self.confidence,
            "character_count": len(self.text),
            "success": True,
            "error": "",
        }


class ImageBatchWorkflowTests(unittest.TestCase):
    def setUp(self):
        TEST_DIR.mkdir(parents=True, exist_ok=True)
        self.outputs = []

    def tearDown(self):
        shutil.rmtree(TEST_DIR, ignore_errors=True)
        for output in self.outputs:
            Path(output).unlink(missing_ok=True)

    def test_natural_filename_order(self):
        for filename in ("chapter10.jpg", "chapter2.jpg", "10.jpg", "2.jpg", "1.jpg"):
            _image(TEST_DIR / filename)
        ordered = [path.name for path in _collect_image_paths(TEST_DIR)]
        self.assertEqual(
            ordered,
            ["1.jpg", "2.jpg", "10.jpg", "chapter2.jpg", "chapter10.jpg"],
        )

    def test_rapidocr_rows_are_sorted_by_position(self):
        output = SimpleNamespace(
            txts=["第二行", "第一行"],
            scores=[0.8, 1.0],
            boxes=[
                [[0, 30], [10, 30], [10, 40], [0, 40]],
                [[0, 0], [10, 0], [10, 10], [0, 10]],
            ],
        )
        provider = RapidOCRProvider(engine=lambda _: output)
        result = provider.extract_page(TEST_DIR / "page.jpg")
        self.assertEqual(result["text"], "第一行\n第二行")
        self.assertAlmostEqual(result["confidence"], 0.9)

    def test_rapidocr_preserves_large_vertical_gaps_as_paragraph_breaks(self):
        output = SimpleNamespace(
            txts=["第一段末行", "第二段首行", "第一段首行"],
            scores=[0.9, 0.9, 0.9],
            boxes=[
                [[0, 30], [10, 30], [10, 40], [0, 40]],
                [[0, 120], [10, 120], [10, 130], [0, 130]],
                [[0, 0], [10, 0], [10, 10], [0, 10]],
            ],
        )
        provider = RapidOCRProvider(engine=lambda _: output)
        result = provider.extract_page(TEST_DIR / "page.jpg")
        self.assertEqual(result["text"], "第一段首行\n第一段末行\n\n第二段首行")

    def test_low_confidence_aborts_without_docx_or_cleanup(self):
        _image(TEST_DIR / "1.jpg")
        with patch("modules.pipeline_controller._recycle_images") as recycle:
            result = process_image_input(
                TEST_DIR,
                provider=PassThroughDeepSeek(),
                vision_provider=PageOCR(confidence=0.2),
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["step"], "OCR_quality")
        self.assertTrue((TEST_DIR / "1.jpg").exists())
        recycle.assert_not_called()

    def test_review_rejection_preserves_original_chunk_safely(self):
        _image(TEST_DIR / "1.jpg")
        with patch("modules.pipeline_controller._recycle_images") as recycle:
            result = process_image_input(
                TEST_DIR,
                provider=RejectingDeepSeek(),
                vision_provider=PageOCR(),
                cleanup_images=False,
            )
        self.assertTrue(result["success"])
        self.outputs.append(result["output"])
        self.assertEqual(result["preserved_chunks"], [1])
        self.assertTrue((TEST_DIR / "1.jpg").exists())
        recycle.assert_not_called()

    def test_success_generates_docx_then_recycles_manifest(self):
        _image(TEST_DIR / "2.jpg")
        _image(TEST_DIR / "1.jpg")
        recycled = []

        def fake_recycle(paths):
            recycled.extend(Path(path).name for path in paths)
            return []

        with patch("modules.pipeline_controller._recycle_images", side_effect=fake_recycle):
            result = process_image_input(
                TEST_DIR,
                provider=PassThroughDeepSeek(),
                vision_provider=PageOCR(),
            )
        self.assertTrue(result["success"])
        self.outputs.append(result["output"])
        self.assertTrue(Path(result["output"]).exists())
        self.assertEqual(recycled, ["1.jpg", "2.jpg"])
        self.assertEqual(result["images_total"], 2)
        self.assertEqual(result["images_ocr_completed"], 2)
        self.assertEqual(result["full_audit_rounds"], 2)

    def test_full_audit_failure_aborts_without_docx_or_cleanup(self):
        _image(TEST_DIR / "1.jpg")
        with patch("modules.pipeline_controller._recycle_images") as recycle:
            result = process_image_input(
                TEST_DIR,
                provider=FailingAuditDeepSeek(),
                vision_provider=PageOCR(),
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["step"], "full_audit")
        self.assertTrue((TEST_DIR / "1.jpg").exists())
        recycle.assert_not_called()

    def test_minimum_slice_invalid_json_aborts_without_docx_or_cleanup(self):
        _image(TEST_DIR / "1.jpg")
        with patch("modules.pipeline_controller._recycle_images") as recycle:
            result = process_image_input(
                TEST_DIR,
                provider=InvalidMinimumAuditDeepSeek(),
                vision_provider=PageOCR(),
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["step"], "full_audit")
        self.assertTrue((TEST_DIR / "1.jpg").exists())
        recycle.assert_not_called()

    def test_strict_long_text_preserves_unapproved_chunk(self):
        original = "这是需要校对的正文。"
        result = correct_image_text_strict(original, RejectingDeepSeek())
        self.assertTrue(result["success"])
        self.assertEqual(result["final_text"], original)
        self.assertEqual(result["preserved_chunks"], [1])

    def test_rejected_semantic_change_is_revised_and_reviewed_again(self):
        provider = RevisingDeepSeek()
        original = "你的敬拜与我的生活。"
        result = correct_image_text_strict(original, provider)
        self.assertTrue(result["success"])
        self.assertEqual(result["final_text"], original)
        self.assertEqual(provider.reviews, 2)

    def test_strict_correction_preserves_paragraph_boundaries_between_chunks(self):
        original = "第一段内容。\n\n第二段内容。\n\n第三段内容。"
        result = correct_image_text_strict(original, PassThroughDeepSeek(), max_length=8)
        self.assertTrue(result["success"])
        self.assertEqual(result["final_text"], original)

    def test_export_artifacts_removed_without_changing_other_lines(self):
        original = "第一页\n正文一\n\n第十章\n正文二\n来自 小米笔记"
        result = clean_image_ocr_text(original)
        self.assertEqual(result["cleaned_text"], "正文一\n\n正文二")
        self.assertEqual(result["removed_watermarks"], ["第一页", "第十章", "来自 小米笔记"])

    def test_model_reformatting_falls_back_to_original_layout(self):
        original = "第一行。\n第二行。\n\n第三行。"
        result = correct_image_text_strict(original, ReformattingDeepSeek())
        self.assertTrue(result["success"])
        self.assertEqual(result["final_text"], original)
        self.assertEqual(result["preserved_chunks"], [1])


if __name__ == "__main__":
    unittest.main()
