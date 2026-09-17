"""Local RapidOCR provider for privacy-preserving image text extraction."""

from pathlib import Path
from statistics import median


class LocalOCRError(RuntimeError):
    """Raised when the local OCR engine cannot process an image."""


def _point_xy(point):
    try:
        return float(point[0]), float(point[1])
    except (IndexError, TypeError, ValueError):
        return 0.0, 0.0


def _box_bounds(box):
    points = [] if box is None else list(box)
    if not points:
        return 0.0, 0.0, 0.0
    coordinates = [_point_xy(point) for point in points]
    return (
        min(y for _, y in coordinates),
        max(y for _, y in coordinates),
        min(x for x, _ in coordinates),
    )


def _normalize_output(output):
    """Return ``(box, text, score)`` rows for current and legacy RapidOCR APIs."""
    if output is None:
        return []

    texts = getattr(output, "txts", None)
    scores = getattr(output, "scores", None)
    boxes = getattr(output, "boxes", None)
    if texts is not None:
        scores = list([0.0] * len(texts) if scores is None else scores)
        boxes = list([None] * len(texts) if boxes is None else boxes)
        return list(zip(boxes, list(texts), scores))

    result = output
    if isinstance(output, tuple) and output:
        result = output[0]
    rows = []
    for item in result or []:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            rows.append((item[0], item[1], item[2]))
    return rows


class RapidOCRProvider:
    """Extract Chinese text locally with RapidOCR and ONNX Runtime."""

    provider_name = "rapidocr"

    def __init__(self, engine=None):
        if engine is not None:
            self.engine = engine
            return
        try:
            from rapidocr import RapidOCR
        except ImportError as error:
            raise LocalOCRError(
                "RapidOCR is not installed. Run setup_image_to_doc.bat first."
            ) from error
        self.engine = RapidOCR()

    def extract_page(self, image_path):
        path = Path(image_path)
        try:
            output = self.engine(str(path))
            rows = _normalize_output(output)
        except Exception as error:
            raise LocalOCRError(f"Local OCR failed for {path.name}: {error}") from error

        normalized = []
        for box, text, score in rows:
            cleaned = str(text or "").strip()
            if not cleaned:
                continue
            try:
                confidence = float(score)
            except (TypeError, ValueError):
                confidence = 0.0
            normalized.append((_box_bounds(box), cleaned, confidence))

        normalized.sort(key=lambda item: (round(item[0][0] / 12), item[0][2], item[0][0]))
        positive_gaps = [
            current[0][0] - previous[0][1]
            for previous, current in zip(normalized, normalized[1:])
            if current[0][0] > previous[0][1]
        ]
        ordered_gaps = sorted(positive_gaps)
        lower_gaps = ordered_gaps[: max(1, len(ordered_gaps) // 2)]
        typical_gap = median(lower_gaps) if lower_gaps else 0.0
        paragraph_gap = max(55.0, typical_gap * 2.2)
        text_parts = []
        for index, item in enumerate(normalized):
            if index:
                gap = item[0][0] - normalized[index - 1][0][1]
                text_parts.append("\n\n" if gap >= paragraph_gap else "\n")
            text_parts.append(item[1])
        text = "".join(text_parts)
        scores = [item[2] for item in normalized]
        return {
            "filename": path.name,
            "text": text,
            "confidence": sum(scores) / len(scores) if scores else 0.0,
            "character_count": sum(1 for character in text if character.isalnum()),
            "success": bool(text),
            "error": "" if text else "No readable text was detected.",
        }
