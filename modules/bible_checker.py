"""Bible terminology checker foundation."""

import json
from difflib import get_close_matches
from pathlib import Path
from modules.resource_path import resource_path


DEFAULT_DATABASE_PATH = resource_path("database/bible_terms.json")
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


def _canonical_term(term):
    """Normalize a term for matching, ignoring book-title brackets."""
    return str(term).replace("《", "").replace("》", "").strip()


def _all_terms(database):
    terms = []
    for category in CATEGORIES:
        for term in database.get(category, []):
            terms.append((category, term))
    return terms


def _canonical_lookup(database):
    """Map canonical term text to its display form and category."""
    lookup = {}
    for category, term in _all_terms(database):
        lookup[_canonical_term(term)] = {"category": category, "display": term}
    return lookup


def _find_category_for_suggestion(database, suggestion):
    lookup = _canonical_lookup(database)
    match = lookup.get(_canonical_term(suggestion))
    if match:
        return match["category"]
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
    lookup = _canonical_lookup(database)
    known_canonical = list(lookup.keys())

    for found, suggestion in database.get("common_mistakes", {}).items():
        if found in text:
            category = _find_category_for_suggestion(database, suggestion)
            display_suggestion = lookup.get(_canonical_term(suggestion), {}).get("display", suggestion)
            _add_issue(
                issues,
                {
                    "type": ISSUE_TYPES.get(category, "terminology"),
                    "found": found,
                    "suggestion": display_suggestion,
                },
            )

    checked_tokens = set(database.get("common_mistakes", {}).keys())

    for raw_token in _candidate_terms(text):
        canonical_token = _canonical_term(raw_token)
        if raw_token in checked_tokens or canonical_token in lookup:
            continue
        if any(known in canonical_token for known in known_canonical):
            continue

        matches = get_close_matches(canonical_token, known_canonical, n=1, cutoff=0.86)
        if matches:
            suggestion = lookup[matches[0]]["display"]
            if _canonical_term(suggestion) != canonical_token:
                category = lookup[matches[0]]["category"]
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
