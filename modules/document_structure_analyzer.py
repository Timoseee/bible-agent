"""Classify document text structure without rewriting content."""

import re


SCRIPTURE_REFERENCE_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,10}(?:记|书|福音|行传)\s*\d+\s*(?:章|篇)?|\d+\s*:\s*\d+")


def analyze_text_structure(text):
    """Detect title, headings, body, and scripture references."""
    structure = {
        "title": [],
        "headings": [],
        "body": [],
        "scripture_references": [],
    }

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        if index == 0 and len(line) <= 40 and not re.search(r"[。！？!?]", line):
            structure["title"].append(line)
        elif re.match(r"^[一二三四五六七八九十]+[、.．]", line) or line.endswith(("：", ":")):
            structure["headings"].append(line)
        elif SCRIPTURE_REFERENCE_PATTERN.search(line):
            structure["scripture_references"].append(line)
        else:
            structure["body"].append(line)

    return structure
