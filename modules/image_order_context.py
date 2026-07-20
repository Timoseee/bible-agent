"""Build AI-readable context for image ordering decisions."""


def build_ordering_context(image_metadata):
    """Convert image metadata into ordering context text."""
    if not image_metadata:
        return "No image metadata available."

    lines = ["Image ordering metadata:"]

    for index, metadata in enumerate(image_metadata, start=1):
        lines.extend(
            [
                "",
                f"Image {index}: {metadata.get('filename', '')}",
                f"Page number: {metadata.get('page_number')}",
                f"Chapter reference: {metadata.get('chapter_reference', '')}",
                f"First text: {metadata.get('first_text', '')}",
                f"Last text: {metadata.get('last_text', '')}",
                f"Confidence: {metadata.get('confidence', 0.0)}",
            ]
        )

    return "\n".join(lines)
