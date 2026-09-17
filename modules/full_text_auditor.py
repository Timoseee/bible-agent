"""Conservative full-document DeepSeek audit with deterministic edit application."""

import json
import re
from dataclasses import dataclass

from modules.ai_provider import AIProviderJSONError
from modules.resource_path import resource_path


AUDIT_PROMPT_PATH = resource_path("prompts/full_text_audit_prompt.txt")
REVIEW_PROMPT_PATH = resource_path("prompts/full_text_audit_review_prompt.txt")
ALLOWED_TYPES = {
    "ocr_error",
    "chinese_typo",
    "bible_name",
    "bible_term",
    "scripture_reference",
}
KNOWN_FIXED_PHRASES = {
    "主任请安": "主内平安",
    "逃暑假": "收赎价",
}


class FullTextAuditError(RuntimeError):
    """Raised when a required audit or review stage cannot be completed safely."""


@dataclass(frozen=True)
class AuditCandidate:
    paragraph_id: str
    original: str
    replacement: str
    error_type: str
    reason: str
    confidence: float

    @property
    def key(self):
        return (self.paragraph_id, self.original, self.replacement)


@dataclass(frozen=True)
class AuditSlice:
    paragraph_index: int
    start: int
    end: int


def _paragraph_id(index):
    return f"P{index + 1:04d}"


def _build_windows(paragraphs, max_characters, overlap_characters):
    """Return paragraph index windows covering the document with bounded overlap."""
    if not paragraphs:
        return []
    windows = []
    start = 0
    total = len(paragraphs)
    while start < total:
        end = start
        size = 0
        while end < total:
            addition = len(paragraphs[end]) + 12
            if end > start and size + addition > max_characters:
                break
            size += addition
            end += 1
        windows.append((start, end))
        if end >= total:
            break
        overlap = 0
        next_start = end
        while next_start > start + 1 and overlap < overlap_characters:
            next_start -= 1
            overlap += len(paragraphs[next_start]) + 12
        start = next_start
    return windows


def _window_content(paragraphs, start, end):
    return "\n".join(
        f"[[{_paragraph_id(index)}]]{paragraphs[index]}"
        for index in range(start, end)
    )


def _segment_content(paragraphs, slices):
    return "\n".join(
        f"[[{_paragraph_id(item.paragraph_index)}]]"
        f"{paragraphs[item.paragraph_index][item.start:item.end]}"
        for item in slices
    )


def _split_segment(paragraphs, slices, minimum_characters, overlap_characters):
    """Split an audit segment without leaving an uncovered text boundary."""
    if len(slices) > 1:
        sizes = [max(1, item.end - item.start) for item in slices]
        target = sum(sizes) / 2
        running = 0
        split_at = 1
        for index, size in enumerate(sizes[:-1], start=1):
            running += size
            split_at = index
            if running >= target:
                break
        return slices[:split_at], slices[split_at:]

    item = slices[0]
    length = item.end - item.start
    if length <= minimum_characters:
        return None

    paragraph = paragraphs[item.paragraph_index]
    midpoint = item.start + length // 2
    boundary_candidates = [
        match.end()
        for match in re.finditer(r"[。！？；!?;]", paragraph[item.start:item.end])
    ]
    boundary_candidates = [item.start + value for value in boundary_candidates]
    usable = [
        value
        for value in boundary_candidates
        if item.start < value < item.end
    ]
    boundary = min(usable, key=lambda value: abs(value - midpoint)) if usable else midpoint
    overlap = min(
        max(0, int(overlap_characters)),
        max(0, (boundary - item.start) // 2),
        max(0, (item.end - boundary) // 2),
    )
    left_end = min(item.end, boundary + overlap)
    right_start = max(item.start, boundary - overlap)
    if left_end >= item.end and right_start <= item.start:
        boundary = midpoint
        overlap = 0
        left_end = boundary
        right_start = boundary
    return (
        [AuditSlice(item.paragraph_index, item.start, left_end)],
        [AuditSlice(item.paragraph_index, right_start, item.end)],
    )


def _load_json_object(response_text, stage):
    try:
        value = json.loads(str(response_text or ""))
    except (json.JSONDecodeError, TypeError) as error:
        raise FullTextAuditError(f"DeepSeek {stage} returned invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise FullTextAuditError(f"DeepSeek {stage} JSON must be an object")
    return value


def _parse_candidates(payload, paragraphs, minimum_confidence, allowed_paragraph_ids=None):
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        raise FullTextAuditError("DeepSeek full audit JSON is missing candidates[]")

    accepted = []
    rejected = 0
    warnings = []
    seen = set()
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            rejected += 1
            continue
        try:
            candidate = AuditCandidate(
                paragraph_id=str(raw.get("paragraph_id", "")).strip(),
                original=str(raw.get("original", "")),
                replacement=str(raw.get("replacement", "")),
                error_type=str(raw.get("error_type", "")).strip(),
                reason=str(raw.get("reason", "")).strip(),
                confidence=float(raw.get("confidence", 0.0)),
            )
        except (TypeError, ValueError):
            rejected += 1
            continue

        try:
            index = int(candidate.paragraph_id[1:]) - 1
        except (ValueError, TypeError):
            index = -1
        valid = (
            candidate.paragraph_id == _paragraph_id(index)
            and 0 <= index < len(paragraphs)
            and candidate.error_type in ALLOWED_TYPES
            and candidate.confidence >= minimum_confidence
            and candidate.original
            and candidate.replacement
            and candidate.original != candidate.replacement
            and "\n" not in candidate.original
            and "\n" not in candidate.replacement
            and len(candidate.original) <= 40
            and len(candidate.replacement) <= 40
            and abs(len(candidate.replacement) - len(candidate.original)) <= 8
            and paragraphs[index].count(candidate.original) == 1
            and (
                allowed_paragraph_ids is None
                or candidate.paragraph_id in allowed_paragraph_ids
            )
        )
        if not valid or candidate.key in seen:
            rejected += 1
            continue
        seen.add(candidate.key)
        accepted.append(candidate)

    if rejected:
        warnings.append(f"Rejected {rejected} invalid, ambiguous, or low-confidence candidates")
    return accepted, rejected, warnings


def _audit_segment(
    paragraphs,
    slices,
    provider,
    prompt,
    minimum_confidence,
    round_index,
    minimum_segment_characters=1000,
    segment_overlap_characters=150,
):
    """Audit one segment, recursively reducing only incomplete JSON responses."""
    try:
        response = provider.generate_json(
            prompt,
            _segment_content(paragraphs, slices),
        )
        payload = _load_json_object(response, f"full audit round {round_index}")
    except AIProviderJSONError as error:
        split_reason = error.error_type
        split = _split_segment(
            paragraphs,
            slices,
            minimum_segment_characters,
            segment_overlap_characters,
        )
        if split is None:
            raise FullTextAuditError(
                f"DeepSeek full audit failed in round {round_index}: {error}"
            ) from error
    except FullTextAuditError as error:
        if "returned invalid JSON" not in str(error):
            raise
        split_reason = "invalid_json"
        split = _split_segment(
            paragraphs,
            slices,
            minimum_segment_characters,
            segment_overlap_characters,
        )
        if split is None:
            raise
    except Exception as error:
        raise FullTextAuditError(
            f"DeepSeek full audit failed in round {round_index}: {error}"
        ) from error
    else:
        allowed_ids = {_paragraph_id(item.paragraph_index) for item in slices}
        return _parse_candidates(
            payload,
            paragraphs,
            minimum_confidence,
            allowed_ids,
        )

    label = "响应过长" if split_reason == "truncated" else "JSON 不完整"
    warning = f"DeepSeek {label}，已自动拆分重试（第 {round_index} 轮）"
    combined_candidates = []
    combined_rejected = 0
    combined_warnings = [warning]
    for child in split:
        candidates, rejected, warnings = _audit_segment(
            paragraphs,
            child,
            provider,
            prompt,
            minimum_confidence,
            round_index,
            minimum_segment_characters,
            segment_overlap_characters,
        )
        combined_candidates.extend(candidates)
        combined_rejected += rejected
        combined_warnings.extend(warnings)
    return combined_candidates, combined_rejected, combined_warnings


def _review_candidates(candidates, paragraphs, provider, batch_size=25):
    if not candidates:
        return set(), 0, []
    approved = set()
    rejected = 0
    warnings = []
    prompt = REVIEW_PROMPT_PATH.read_text(encoding="utf-8").strip()
    for offset in range(0, len(candidates), batch_size):
        batch = candidates[offset : offset + batch_size]
        records = []
        for position, candidate in enumerate(batch, start=offset + 1):
            paragraph_index = int(candidate.paragraph_id[1:]) - 1
            records.append(
                {
                    "id": f"C{position:04d}",
                    "paragraph_id": candidate.paragraph_id,
                    "paragraph": paragraphs[paragraph_index],
                    "original": candidate.original,
                    "replacement": candidate.replacement,
                    "error_type": candidate.error_type,
                    "reason": candidate.reason,
                }
            )
        try:
            response = provider.generate_json(
                prompt,
                json.dumps({"candidates": records}, ensure_ascii=False),
            )
        except Exception as error:
            raise FullTextAuditError(f"DeepSeek candidate review failed: {error}") from error
        payload = _load_json_object(response, "candidate review")
        decisions = payload.get("decisions")
        if not isinstance(decisions, list):
            raise FullTextAuditError("DeepSeek candidate review JSON is missing decisions[]")
        expected_replacements = {
            f"C{position:04d}": candidate.replacement
            for position, candidate in enumerate(batch, start=offset + 1)
        }
        decision_map = {}
        for item in decisions:
            if not isinstance(item, dict):
                continue
            candidate_id = str(item.get("id", ""))
            decision_map[candidate_id] = bool(item.get("approved", False)) and (
                str(item.get("verified_replacement", ""))
                == expected_replacements.get(candidate_id, "")
            )
        for position, candidate in enumerate(batch, start=offset + 1):
            candidate_id = f"C{position:04d}"
            if decision_map.get(candidate_id, False):
                approved.add(candidate.key)
            else:
                rejected += 1
        missing = len(batch) - sum(
            1 for position in range(offset + 1, offset + len(batch) + 1)
            if f"C{position:04d}" in decision_map
        )
        if missing:
            warnings.append(f"Reviewer omitted {missing} decisions; candidates were rejected")
    return approved, rejected, warnings


def _apply_candidates(paragraphs, candidates, approved_keys):
    by_paragraph = {}
    rejected = 0
    for candidate in candidates:
        if candidate.key not in approved_keys:
            continue
        index = int(candidate.paragraph_id[1:]) - 1
        start = paragraphs[index].find(candidate.original)
        if start < 0 or paragraphs[index].count(candidate.original) != 1:
            rejected += 1
            continue
        by_paragraph.setdefault(index, []).append((start, candidate))

    applied = []
    for paragraph_index, edits in by_paragraph.items():
        edits.sort(key=lambda item: item[0])
        previous_end = -1
        non_conflicting = []
        for start, candidate in edits:
            end = start + len(candidate.original)
            if start < previous_end:
                rejected += 1
                continue
            non_conflicting.append((start, end, candidate))
            previous_end = end
        value = paragraphs[paragraph_index]
        before = value
        for start, end, candidate in reversed(non_conflicting):
            value = value[:start] + candidate.replacement + value[end:]
            applied.append(
                {
                    "paragraph_id": candidate.paragraph_id,
                    "original": candidate.original,
                    "replacement": candidate.replacement,
                    "error_type": candidate.error_type,
                    "reason": candidate.reason,
                    "confidence": candidate.confidence,
                }
            )
        paragraphs[paragraph_index] = value
        if before == value and non_conflicting:
            raise FullTextAuditError("Approved audit edits did not change the target paragraph")
    return applied, rejected


def _summarize_warnings(warnings):
    summarized = []
    split_counts = {}
    for warning in warnings:
        if "自动拆分重试" in warning:
            split_counts[warning] = split_counts.get(warning, 0) + 1
        else:
            summarized.append(warning)
    summarized.extend(
        f"{warning}（共 {count} 次）"
        for warning, count in split_counts.items()
    )
    return summarized


def audit_paragraphs(
    paragraphs,
    provider,
    *,
    rounds=2,
    max_characters=6000,
    overlap_characters=600,
    minimum_confidence=0.92,
):
    """Audit natural paragraphs twice and apply only independently approved edits."""
    if provider is None or not hasattr(provider, "generate_json"):
        raise FullTextAuditError("A DeepSeek provider with JSON support is required")
    current = [str(paragraph) for paragraph in paragraphs]
    if not current or not any(paragraph.strip() for paragraph in current):
        raise FullTextAuditError("Full audit text is empty")
    original_count = len(current)
    total_candidates = 0
    total_rejected = 0
    applied_edits = []
    warnings = []
    audit_prompt = AUDIT_PROMPT_PATH.read_text(encoding="utf-8").strip()

    for round_index in range(1, rounds + 1):
        round_candidates = []
        round_window_size = (
            max_characters
            if round_index == 1
            else max(1500, max_characters // 2)
        )
        for start, end in _build_windows(
            current, round_window_size, overlap_characters
        ):
            slices = [
                AuditSlice(index, 0, len(current[index]))
                for index in range(start, end)
            ]
            candidates, rejected, candidate_warnings = _audit_segment(
                current,
                slices,
                provider,
                audit_prompt,
                minimum_confidence,
                round_index,
            )
            round_candidates.extend(candidates)
            total_rejected += rejected
            warnings.extend(candidate_warnings)

        seeded_candidates = []
        for paragraph_index, paragraph in enumerate(current):
            for original, replacement in KNOWN_FIXED_PHRASES.items():
                if paragraph.count(original) == 1:
                    seeded_candidates.append(
                        AuditCandidate(
                            paragraph_id=_paragraph_id(paragraph_index),
                            original=original,
                            replacement=replacement,
                            error_type="ocr_error",
                            reason="Verified Bible-sermon fixed phrase was misrecognized by OCR",
                            confidence=0.99,
                        )
                    )
        seeded_targets = {
            (candidate.paragraph_id, candidate.original)
            for candidate in seeded_candidates
        }
        round_candidates = [
            candidate
            for candidate in round_candidates
            if (candidate.paragraph_id, candidate.original) not in seeded_targets
        ] + seeded_candidates

        deduplicated = {candidate.key: candidate for candidate in round_candidates}
        candidates = list(deduplicated.values())
        total_candidates += len(candidates)
        approved, review_rejected, review_warnings = _review_candidates(
            candidates, current, provider
        )
        total_rejected += review_rejected
        warnings.extend(review_warnings)
        applied, conflict_rejected = _apply_candidates(current, candidates, approved)
        applied_edits.extend(applied)
        total_rejected += conflict_rejected

        if len(current) != original_count:
            raise FullTextAuditError("Full audit changed the paragraph count")

    return {
        "success": True,
        "paragraphs": current,
        "final_text": "\n\n".join(current),
        "full_audit_candidates": total_candidates,
        "full_audit_applied": len(applied_edits),
        "full_audit_rejected": total_rejected,
        "full_audit_rounds": rounds,
        "audit_warnings": _summarize_warnings(warnings),
        "applied_edits": applied_edits,
    }
