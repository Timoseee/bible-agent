"""Phase 6B tests for image ordering and chapter metadata."""

import unittest
from pathlib import Path

from modules.image_analyzer import analyze_image
from modules.image_sorter import sort_images


class MockImageAnalysisProvider:
    def __init__(self, metadata_by_name, sort_result=None):
        self.metadata_by_name = metadata_by_name
        self.sort_result = sort_result

    def analyze_image(self, image_path):
        filename = Path(image_path).name
        metadata = {
            "filename": filename,
            "page_number": None,
            "chapter_reference": "",
            "first_text": "",
            "last_text": "",
            "confidence": 0.0,
        }
        metadata.update(self.metadata_by_name.get(filename, {}))
        return metadata

    def sort_images(self, context, metadata):
        _ = (context, metadata)
        return self.sort_result or {"ordered_filenames": [], "confidence": 0.0}


class Phase6BImageOrderingTests(unittest.TestCase):
    def test_filename_order_should_not_determine_result(self):
        paths = [Path("IMG_005.png"), Path("IMG_001.png"), Path("IMG_003.png")]
        provider = MockImageAnalysisProvider(
            {
                "IMG_005.png": {"page_number": 2, "confidence": 0.95},
                "IMG_001.png": {"page_number": 3, "confidence": 0.95},
                "IMG_003.png": {"page_number": 1, "confidence": 0.95},
            }
        )
        result = sort_images(paths, provider)
        self.assertEqual(
            [Path(path).name for path in result["ordered_images"]],
            ["IMG_003.png", "IMG_005.png", "IMG_001.png"],
        )

    def test_page_number_sorting_works(self):
        paths = [Path("page3.png"), Path("page1.png"), Path("page2.png")]
        provider = MockImageAnalysisProvider(
            {
                "page3.png": {"page_number": 3, "confidence": 0.95},
                "page1.png": {"page_number": 1, "confidence": 0.95},
                "page2.png": {"page_number": 2, "confidence": 0.95},
            }
        )
        result = sort_images(paths, provider)
        self.assertEqual([Path(path).stem for path in result["ordered_images"]], ["page1", "page2", "page3"])
        self.assertGreaterEqual(result["confidence"], 0.9)

    def test_chapter_reference_metadata_extraction(self):
        provider = MockImageAnalysisProvider(
            {
                "chapter.png": {
                    "chapter_reference": "出埃及记24章",
                    "first_text": "出埃及记24章",
                    "confidence": 0.8,
                }
            }
        )
        metadata = analyze_image(Path("chapter.png"), provider)
        self.assertEqual(metadata["chapter_reference"], "出埃及记24章")
        self.assertEqual(metadata["first_text"], "出埃及记24章")

    def test_low_confidence_returns_warning(self):
        paths = [Path("a.png"), Path("b.png")]
        provider = MockImageAnalysisProvider(
            {
                "a.png": {"first_text": "A", "confidence": 0.2},
                "b.png": {"first_text": "B", "confidence": 0.2},
            }
        )
        result = sort_images(paths, provider)
        self.assertEqual([Path(path).name for path in result["ordered_images"]], ["a.png", "b.png"])
        self.assertEqual(result["warning"], "Unable to confidently determine order")

    def test_mock_vision_provider_works_for_ai_judgment(self):
        paths = [Path("second.png"), Path("first.png")]
        provider = MockImageAnalysisProvider(
            {
                "second.png": {"last_text": "end", "confidence": 0.5},
                "first.png": {"first_text": "begin", "confidence": 0.5},
            },
            sort_result={"ordered_filenames": ["first.png", "second.png"], "confidence": 0.82},
        )
        result = sort_images(paths, provider)
        self.assertEqual([Path(path).name for path in result["ordered_images"]], ["first.png", "second.png"])

    def test_empty_folder_handling(self):
        result = sort_images([], MockImageAnalysisProvider({}))
        self.assertEqual(result["ordered_images"], [])
        self.assertEqual(result["warning"], "No images provided")


if __name__ == "__main__":
    unittest.main()
