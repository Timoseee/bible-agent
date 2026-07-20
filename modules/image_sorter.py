"""Content-based image ordering helpers."""

from pathlib import Path

from modules.image_analyzer import analyze_image
from modules.image_order_context import build_ordering_context


LOW_CONFIDENCE_WARNING = "Unable to confidently determine order"


def _sort_by_page_number(metadata):
    if not metadata or any(item.get("page_number") is None for item in metadata):
        return None

    page_numbers = [item["page_number"] for item in metadata]
    if len(set(page_numbers)) != len(page_numbers):
        return None

    ordered = sorted(metadata, key=lambda item: item["page_number"])
    confidence = min(item.get("confidence", 0.0) for item in ordered)
    return ordered, max(confidence, 0.9)


def _sort_by_provider(metadata, provider):
    if provider is None or not hasattr(provider, "sort_images"):
        return None

    context = build_ordering_context(metadata)
    order = provider.sort_images(context, metadata)
    lookup = {item["filename"]: item for item in metadata}
    ordered = [lookup[name] for name in order.get("ordered_filenames", []) if name in lookup]

    if len(ordered) != len(metadata):
        return None

    return ordered, float(order.get("confidence", 0.0))


def sort_images(image_paths, provider=None):
    """Sort images using metadata, with conservative fallback on low confidence."""
    original_paths = [Path(path) for path in image_paths]

    if not original_paths:
        return {
            "ordered_images": [],
            "confidence": 0.0,
            "warning": "No images provided",
            "metadata": [],
        }

    metadata = [analyze_image(path, provider) for path in original_paths]

    strategy_result = _sort_by_page_number(metadata)
    if strategy_result is None:
        strategy_result = _sort_by_provider(metadata, provider)

    if strategy_result is None:
        return {
            "ordered_images": [str(path) for path in original_paths],
            "confidence": 0.0,
            "warning": LOW_CONFIDENCE_WARNING,
            "metadata": metadata,
        }

    ordered_metadata, confidence = strategy_result

    if confidence < 0.6:
        return {
            "ordered_images": [str(path) for path in original_paths],
            "confidence": confidence,
            "warning": LOW_CONFIDENCE_WARNING,
            "metadata": metadata,
        }

    path_lookup = {path.name: str(path) for path in original_paths}
    return {
        "ordered_images": [path_lookup[item["filename"]] for item in ordered_metadata],
        "confidence": round(confidence, 2),
        "metadata": metadata,
    }
