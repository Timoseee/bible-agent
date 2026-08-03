"""Review agent for checking corrected sermon text."""

import json
from modules.resource_path import resource_path


REVIEW_PROMPT_PATH = resource_path("prompts/review_prompt.txt")


def load_review_prompt():
    """Load the review prompt used by the AI provider."""
    return REVIEW_PROMPT_PATH.read_text(encoding="utf-8").strip()


def _parse_review_response(response_text):
    try:
        review = json.loads(response_text)
    except json.JSONDecodeError:
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
    response_text = provider.generate(prompt, content)
    return _parse_review_response(response_text)
