"""Bible terminology checker foundation."""

import json
from difflib import get_close_matches
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = BASE_DIR / "database" / "bible_terms.json"
CATEGORIES = ("books", "people", "places", "terms")
ISSUE_TYPES = {
    "books": "book_name",
    "people": "person_name",
    "places": "place_name",
    "terms": "terminology",
}


def load_bible_database(database_path=DEFAULT_DATABASE_PATH):
    """Load Bible terminology data from JSON."""
    path = Path(database_path)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _all_terms(database):
    terms = []
    for category in CATEGORIES:
        for term in database.get(category, []):
            terms.append((category, term))
    return terms


def _find_category_for_suggestion(database, suggestion):
    for category in CATEGORIES:
        if suggestion in database.get(category, []):
            return category
    return "terms"


def _add_issue(issues, issue):
    marker = (issue["type"], issue["found"], issue["suggestion"])
    existing = {(item["type"], item["found"], item["suggestion"]) for item in issues}
    if marker not in existing:
        issues.append(issue)


def check_bible_terms(text, database=None):
    """Report possible Bible terminology issues without modifying text."""
    if not text:
        return {"issues": []}

    database = database or load_bible_database()
    issues = []

    for found, suggestion in database.get("common_mistakes", {}).items():
        if found in text:
            category = _find_category_for_suggestion(database, suggestion)
            _add_issue(
                issues,
                {
                    "type": ISSUE_TYPES.get(category, "terminology"),
                    "found": found,
                    "suggestion": suggestion,
                },
            )

    known_terms = _all_terms(database)
    known_values = [term for _, term in known_terms]
    checked_tokens = set(database.get("common_mistakes", {}).keys())

    for raw_token in _candidate_terms(text):
        if raw_token in checked_tokens or raw_token in known_values:
            continue
        if any(known_value in raw_token for known_value in known_values):
            continue

        matches = get_close_matches(raw_token, known_values, n=1, cutoff=0.86)
        if matches:
            suggestion = matches[0]
            if suggestion != raw_token:
                category = _find_category_for_suggestion(database, suggestion)
                _add_issue(
                    issues,
                    {
                        "type": ISSUE_TYPES.get(category, "terminology"),
                        "found": raw_token,
                        "suggestion": suggestion,
                    },
                )

    return {"issues": issues}


def _candidate_terms(text):
    """Create short Chinese candidate strings for conservative fuzzy matching."""
    candidates = set()
    text_length = len(text)

    for start in range(text_length):
        for size in range(2, 8):
            end = start + size
            if end <= text_length:
                token = text[start:end]
                if all("\u4e00" <= char <= "\u9fff" for char in token):
                    candidates.add(token)

    return candidates
