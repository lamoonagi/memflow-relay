"""Unit tests for security/redaction.py."""
from __future__ import annotations

import pytest

from memflow_relay.security.redaction import (
    _clear_runtime_secrets,
    redact,
    redact_headers,
    register_secret,
)

GEMINI_KEY = "AIzaSyFakeGeminiKey123456789abcdefghij"
MEMFLOW_KEY = "lago_fakekey1234567890abcde"
BEARER_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.fakepayload.fakesig"


class TestRedact:
    def test_redacts_lago_token(self):
        text = f"key={MEMFLOW_KEY}&other=value"
        result = redact(text)
        assert MEMFLOW_KEY not in result
        assert "[REDACTED]" in result

    def test_redacts_bearer_token(self):
        # Bearer token in a plain (non-Authorization-header) context:
        # the _BEARER_RE retains the "Bearer " prefix.
        text = f"token is Bearer {BEARER_TOKEN} in body"
        result = redact(text)
        assert BEARER_TOKEN not in result
        assert "[REDACTED]" in result

    def test_redacts_authorization_header_line(self):
        # Full "Authorization: Bearer ..." header line — _AUTH_HEADER_RE
        # replaces everything after "Authorization: " with [REDACTED].
        text = f"Authorization: Bearer {BEARER_TOKEN}"
        result = redact(text)
        assert BEARER_TOKEN not in result
        assert "[REDACTED]" in result
        assert "Authorization:" in result

    def test_redacts_auth_header(self):
        text = "authorization: lago_fakekey1234567890abcde"
        result = redact(text)
        assert "lago_fakekey" not in result

    def test_redacts_cookie_header(self):
        text = "cookie: session=abc123; token=xyz789"
        result = redact(text)
        assert "abc123" not in result

    def test_empty_string_unchanged(self):
        assert redact("") == ""

    def test_no_secrets_unchanged(self):
        plain = "hello world 123"
        assert redact(plain) == plain

    def test_api_key_kv_pattern(self):
        text = 'api_key="secretvalue123456789"'
        result = redact(text)
        assert "secretvalue123456789" not in result

    def test_password_kv_pattern(self):
        text = "password=hunter2hunter2"
        result = redact(text)
        assert "hunter2hunter2" not in result


class TestRegisterSecret:
    def test_registered_secret_is_redacted(self):
        secret = "verysecretliteralvalue42"
        register_secret(secret)
        result = redact(f"The secret is {secret} in the text.")
        assert secret not in result
        assert "[REDACTED]" in result

    def test_empty_string_not_registered(self):
        register_secret("")
        result = redact("some text")
        assert result == "some text"

    def test_duplicate_registration_no_error(self):
        register_secret("lago_fakekey1234567890abcde")
        register_secret("lago_fakekey1234567890abcde")  # should not raise


class TestRedactHeaders:
    def test_authorization_redacted(self):
        headers = {"Authorization": "Bearer tok123", "Content-Type": "application/json"}
        result = redact_headers(headers)
        assert result["Authorization"] == "[REDACTED]"
        assert result["Content-Type"] == "application/json"

    def test_cookie_redacted(self):
        headers = {"cookie": "session=abc", "accept": "application/json"}
        result = redact_headers(headers)
        assert result["cookie"] == "[REDACTED]"
        assert result["accept"] == "application/json"

    def test_x_goog_api_key_redacted(self):
        headers = {"x-goog-api-key": "AIzaSyFake", "content-type": "application/json"}
        result = redact_headers(headers)
        assert result["x-goog-api-key"] == "[REDACTED]"

    def test_x_api_key_redacted(self):
        headers = {"x-api-key": "somekey", "host": "example.com"}
        result = redact_headers(headers)
        assert result["x-api-key"] == "[REDACTED]"
        assert result["host"] == "example.com"

    def test_original_headers_not_mutated(self):
        original = {"Authorization": "Bearer tok", "Content-Type": "text/plain"}
        redact_headers(original)
        assert original["Authorization"] == "Bearer tok"


class TestGeminiKeyNeverInOutput:
    """Verify GEMINI_API_KEY never appears in redacted output."""

    def test_gemini_key_registered_and_redacted(self):
        """Simulate startup: register Gemini key, then verify it's scrubbed."""
        register_secret(GEMINI_KEY)
        text = f"Sending request with key {GEMINI_KEY} to Gemini"
        result = redact(text)
        assert GEMINI_KEY not in result
        assert "[REDACTED]" in result

    def test_gemini_key_in_json_redacted(self):
        """Gemini key embedded in a JSON-like string is redacted."""
        import json
        payload = json.dumps({"x-goog-api-key": GEMINI_KEY, "model": "gemini-1.5-pro"})
        register_secret(GEMINI_KEY)
        result = redact(payload)
        assert GEMINI_KEY not in result
