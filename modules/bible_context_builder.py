"""Build AI-readable context from Bible checker issues."""


TYPE_LABELS = {
    "book_name": "Bible book name",
    "person_name": "Bible person name",
    "place_name": "Bible place name",
    "terminology": "Bible terminology",
}


def build_bible_context(issues):
    """Convert Bible checker issues into correction-agent context."""
    if not issues:
        return "No possible Bible terminology issues detected."

    lines = ["Detected possible Bible terminology issues:"]

    for index, issue in enumerate(issues, start=1):
        issue_type = TYPE_LABELS.get(issue.get("type"), issue.get("type", "Bible terminology"))
        lines.extend(
            [
                "",
                f"{index}.",
                f"Original: {issue.get('found', '')}",
                f"Suggestion: {issue.get('suggestion', '')}",
                f"Type: {issue_type}",
            ]
        )

    lines.extend(
        [
            "",
            "Instruction: Use these suggestions only when they are clear transcription or spelling errors.",
            "If uncertain, keep the original wording.",
        ]
    )

    return "\n".join(lines)
