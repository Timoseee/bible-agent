"""Phase 5A tests for Bible terminology checker foundation."""

import unittest

from modules.bible_checker import check_bible_terms, load_bible_database


class Phase5ABibleCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = load_bible_database()

    def test_correct_bible_term_produces_no_issue(self):
        result = check_bible_terms("摩西带领百姓出埃及。", self.database)
        self.assertEqual(result["issues"], [])

    def test_incorrect_book_name_detected(self):
        result = check_bible_terms("创世纪中记载神创造天地。", self.database)
        self.assertEqual(result["issues"][0]["type"], "book_name")
        self.assertEqual(result["issues"][0]["found"], "创世纪")
        self.assertEqual(result["issues"][0]["suggestion"], "创世记")

    def test_bible_place_detected_as_valid(self):
        result = check_bible_terms("耶路撒冷是重要的地方。", self.database)
        self.assertEqual(result["issues"], [])

    def test_unknown_normal_chinese_words_ignored(self):
        result = check_bible_terms("今天我们一起学习和分享。", self.database)
        self.assertEqual(result["issues"], [])

    def test_empty_text_handled(self):
        result = check_bible_terms("", self.database)
        self.assertEqual(result["issues"], [])


if __name__ == "__main__":
    unittest.main()
