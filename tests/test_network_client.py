"""Tests for explicit API proxy handling and actionable network errors."""

import os
import unittest
from unittest.mock import patch

import httpx
from openai import APIConnectionError, APITimeoutError, AuthenticationError

from modules.network_client import (
    NetworkConfigurationError,
    build_http_client,
    create_openai_client,
    describe_api_error,
    validate_api_proxy,
)


class NetworkClientTests(unittest.TestCase):
    def test_environment_proxy_is_ignored_by_default(self):
        env = {
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
        }
        with patch.dict(os.environ, env, clear=False), patch(
            "modules.network_client.httpx.Client"
        ) as mock_client:
            build_http_client()

        options = mock_client.call_args.kwargs
        self.assertFalse(options["trust_env"])
        self.assertIsNone(options["proxy"])

    def test_explicit_proxy_is_used(self):
        with patch("modules.network_client.httpx.Client") as mock_client:
            build_http_client(proxy="http://127.0.0.1:7890")

        options = mock_client.call_args.kwargs
        self.assertFalse(options["trust_env"])
        self.assertEqual(options["proxy"], "http://127.0.0.1:7890")

    def test_openai_client_uses_two_sdk_retries(self):
        with patch("modules.network_client.build_http_client", return_value=object()), patch(
            "modules.network_client.OpenAI"
        ) as mock_openai:
            create_openai_client("test-key")

        self.assertEqual(mock_openai.call_args.kwargs["max_retries"], 2)

    def test_proxy_validation(self):
        self.assertEqual(validate_api_proxy(""), "")
        self.assertEqual(
            validate_api_proxy(" https://proxy.example:8443 "),
            "https://proxy.example:8443",
        )
        with self.assertRaises(NetworkConfigurationError):
            validate_api_proxy("127.0.0.1:7890")

    def test_connection_timeout_and_authentication_messages(self):
        request = httpx.Request("GET", "https://api.openai.com/v1/models")
        response = httpx.Response(401, request=request)
        errors = [
            (APIConnectionError(request=request), "connection failed"),
            (APITimeoutError(request), "timed out"),
            (AuthenticationError("bad key", response=response, body=None), "authentication failed"),
        ]

        for error, expected in errors:
            with self.subTest(error=type(error).__name__):
                self.assertIn(expected, describe_api_error("OpenAI", error))


if __name__ == "__main__":
    unittest.main()
