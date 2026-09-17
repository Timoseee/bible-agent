"""DeepSeek provider implementation for AI text generation."""

import json
import re
import time

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAIError, RateLimitError

from modules.ai_provider import AIProvider, AIProviderError, AIProviderJSONError
from modules.network_client import create_openai_client, describe_api_error


class DeepSeekProvider(AIProvider):
    """DeepSeek API provider following the AIProvider interface."""

    provider_name = "deepseek"
    base_url = "https://api.deepseek.com"
    model = "deepseek-v4-flash"

    def __init__(self, api_key, proxy="", model=None, timeout=600.0, max_retries=3):
        if not api_key:
            raise AIProviderError("DEEPSEEK_API_KEY is not configured in .env.")

        self.api_key = api_key
        self.model = str(model or self.model).strip()
        self.json_max_attempts = max(1, int(max_retries))
        self.request_max_attempts = max(1, int(max_retries))
        self.proxy = proxy
        self.timeout = timeout
        self.client = self._new_client()

    def _new_client(self):
        return create_openai_client(
            self.api_key,
            base_url=self.base_url,
            proxy=self.proxy,
            timeout=self.timeout,
            max_retries=0,
        )

    def _reset_client(self):
        try:
            self.client.close()
        except Exception:
            pass
        self.client = self._new_client()

    @staticmethod
    def _is_retryable(error):
        if isinstance(error, (APIConnectionError, APITimeoutError, RateLimitError)):
            return True
        return isinstance(error, APIStatusError) and int(error.status_code) >= 500

    def _request_completion(self, prompt, content, response_format=None, max_tokens=None):
        last_error = None
        for attempt in range(1, self.request_max_attempts + 1):
            try:
                return self._create_completion(
                    prompt,
                    content,
                    response_format=response_format,
                    max_tokens=max_tokens,
                )
            except OpenAIError as error:
                last_error = error
                if not self._is_retryable(error) or attempt >= self.request_max_attempts:
                    raise
                time.sleep(min(2 ** (attempt - 1), 8))
                self._reset_client()
        raise last_error

    def _create_completion(self, prompt, content, response_format=None, max_tokens=None):
        options = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
            "extra_body": {"thinking": {"type": "disabled"}},
        }
        if response_format is not None:
            options["response_format"] = response_format
        if max_tokens is not None:
            options["max_tokens"] = int(max_tokens)
        return self.client.chat.completions.create(**options)

    def generate(self, prompt, content):
        """Send prompt and content to DeepSeek and return response text."""
        try:
            response = self._request_completion(prompt, content)
        except OpenAIError as error:
            raise AIProviderError(describe_api_error("DeepSeek", error)) from error

        return response.choices[0].message.content

    def generate_json(self, prompt, content):
        """Return strict JSON text through DeepSeek's JSON response mode."""
        last_text = ""
        last_finish_reason = ""
        last_error_type = "invalid_json"
        for attempt in range(1, self.json_max_attempts + 1):
            try:
                response = self._request_completion(
                    prompt,
                    content,
                    response_format={"type": "json_object"},
                    max_tokens=8192,
                )
            except OpenAIError as error:
                raise AIProviderError(describe_api_error("DeepSeek", error)) from error

            choice = response.choices[0]
            last_finish_reason = str(getattr(choice, "finish_reason", "") or "")
            last_text = str(choice.message.content or "").strip()
            candidate = self._extract_json_text(last_text)
            try:
                json.loads(candidate)
                return candidate
            except (json.JSONDecodeError, TypeError) as error:
                last_error_type = self._json_error_type(
                    last_text,
                    candidate,
                    last_finish_reason,
                    error,
                )
                if last_error_type == "truncated":
                    break
                if attempt < self.json_max_attempts:
                    continue

        preview = re.sub(r"\s+", " ", last_text)[:160]
        suffix = f" Last response: {preview}" if preview else " The response was empty."
        attempts = 1 if last_error_type == "truncated" else self.json_max_attempts
        if last_error_type == "truncated":
            description = "DeepSeek JSON response was truncated"
        elif last_error_type == "empty":
            description = "DeepSeek returned an empty JSON response"
        else:
            description = "DeepSeek returned invalid JSON"
        finish_suffix = (
            f" finish_reason={last_finish_reason}." if last_finish_reason else ""
        )
        raise AIProviderJSONError(
            f"{description} after {attempts} attempt(s).{finish_suffix}{suffix}",
            error_type=last_error_type,
            finish_reason=last_finish_reason,
            preview=preview,
        )

    @staticmethod
    def _json_error_type(response_text, candidate, finish_reason, decode_error):
        if not str(response_text or "").strip():
            return "empty"
        if str(finish_reason or "").lower() == "length":
            return "truncated"
        text = str(candidate or "").strip()
        if text.startswith(("{", "[")):
            opening = text[0]
            closing = "}" if opening == "{" else "]"
            if not text.endswith(closing):
                return "truncated"
            if isinstance(decode_error, json.JSONDecodeError):
                tail_distance = max(0, len(text) - int(decode_error.pos))
                if tail_distance <= 2 and "Unterminated string" in decode_error.msg:
                    return "truncated"
        return "invalid_json"

    @staticmethod
    def _extract_json_text(response_text):
        text = str(response_text or "").strip().lstrip("\ufeff")
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return text[start : end + 1]
        return text
