"""Phase 6A tests for image OCR extraction."""

import unittest
from pathlib import Path

from PIL import Image

from modules.image_ocr import extract_text_from_image, extract_text_from_images


TEST_DIR = Path(__file__).resolve().parent / "tmp_phase6a"


class MockVisionProvider:
    def __init__(self):
        self.image_paths = []

    def generate_from_image(self, prompt, image_path):
        self.image_paths.append(Path(image_path).name)
        if "empty" in Path(image_path).stem:
            return ""
        return f"text from {Path(image_path).name}"


def _create_test_image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (20, 20), color="white")
    image.save(path)


class Phase6AImageOCRTests(unittest.TestCase):
    def setUp(self):
        TEST_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        for item in TEST_DIR.glob("*"):
            item.unlink()
        TEST_DIR.rmdir()

    def test_valid_image_path_handling(self):
        image_path = TEST_DIR / "page001.png"
        _create_test_image(image_path)
        result = extract_text_from_image(image_path, MockVisionProvider())
        self.assertTrue(result["success"])
        self.assertEqual(result["filename"], "page001.png")

    def test_invalid_image_path_handling(self):
        result = extract_text_from_image(TEST_DIR / "missing.png", MockVisionProvider())
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Image file does not exist.")

    def test_unsupported_format_handling(self):
        text_path = TEST_DIR / "page001.txt"
        text_path.write_text("not an image", encoding="utf-8")
        result = extract_text_from_image(text_path, MockVisionProvider())
        self.assertFalse(result["success"])
        self.assertIn("Unsupported image format", result["error"])

    def test_mock_vision_provider_response(self):
        image_path = TEST_DIR / "page002.jpg"
        _create_test_image(image_path)
        result = extract_text_from_image(image_path, MockVisionProvider())
        self.assertEqual(result["text"], "text from page002.jpg")

    def test_multiple_image_extraction_preserves_order(self):
        image_one = TEST_DIR / "b.png"
        image_two = TEST_DIR / "a.png"
        _create_test_image(image_one)
        _create_test_image(image_two)
        provider = MockVisionProvider()
        result = extract_text_from_images([image_one, image_two], provider)
        self.assertEqual(provider.image_paths, ["b.png", "a.png"])
        self.assertIn("[IMAGE_001]\n\ntext from b.png", result["text"])
        self.assertIn("[IMAGE_002]\n\ntext from a.png", result["text"])

    def test_empty_ocr_result_handling(self):
        image_path = TEST_DIR / "empty.png"
        _create_test_image(image_path)
        result = extract_text_from_image(image_path, MockVisionProvider())
        self.assertTrue(result["success"])
        self.assertEqual(result["text"], "")


if __name__ == "__main__":
    unittest.main()
