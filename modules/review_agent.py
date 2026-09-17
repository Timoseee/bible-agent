"""Review agent for checking corrected sermon text."""

import json
import re
from modules.ai_provider import AIProviderJSONError
from modules.resource_path import resource_path


REVIEW_PROMPT_PATH = resource_path("prompts/review_prompt.txt")
COMPACT_REVIEW_RETRY_SUFFIX = """

The previous JSON response was incomplete. Return a minimal decision only.
Do not explain individual changes and do not repeat any source text.
Use exactly this compact shape and close the JSON object:
{"approved":true,"issues":[],"summary":"通过"}
or
{"approved":false,"issues":[],"summary":"不通过"}
"""


def load_review_prompt():
    """Load the review prompt used by the AI provider."""
    return REVIEW_PROMPT_PATH.read_text(encoding="utf-8").strip()


def _parse_review_response(response_text):
    normalized = str(response_text or "").strip().lstrip("\ufeff")
    if normalized.startswith("```"):
        normalized = re.sub(r"^```(?:json)?\s*", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s*```$", "", normalized)
    start = normalized.find("{")
    end = normalized.rfind("}")
    if start >= 0 and end > start:
        normalized = normalized[start : end + 1]
    try:
        review = json.loads(normalized)
    except (json.JSONDecodeError, TypeError):
        return {
            "approved": False,
            "issues": [
                {
                    "type": "invalid_review_response",
                    "original": "",
                    "corrected": "",
                    "reason": "Review provider did not return valid JSON.",
                }
            ],
            "summary": "Review failed because the provider response was not valid JSON.",
        }

    return {
        "approved": bool(review.get("approved", False)),
        "issues": review.get("issues", []),
        "summary": review.get("summary", ""),
    }


def review_correction(original_text, corrected_text, provider):
    """Ask an AI provider to review whether correction preserved content."""
    if provider is None or not hasattr(provider, "generate"):
        return {
            "approved": False,
            "issues": [
                {
                    "type": "missing_provider",
                    "original": "",
                    "corrected": "",
                    "reason": "A valid AI provider is required.",
                }
            ],
            "summary": "Review could not run because no valid provider was supplied.",
        }

    prompt = load_review_prompt()
    content = (
        "Original text:\n"
        f"{original_text}\n\n"
        "Corrected text:\n"
        f"{corrected_text}"
    )
    if hasattr(provider, "generate_json"):
        try:
            response_text = provider.generate_json(prompt, content)
        except AIProviderJSONError:
            response_text = provider.generate_json(
                prompt + COMPACT_REVIEW_RETRY_SUFFIX,
                content,
            )
    else:
        response_text = provider.generate(prompt, content)
    return _parse_review_response(response_text)
