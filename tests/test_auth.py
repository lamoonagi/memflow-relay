"""Unit tests for auth.py."""
from __future__ import annotations

import pytest

from memflow_relay.auth import (
    is_valid_memflow_key,
    memflow_auth_headers,
    validate_memflow_api_key,
)
from memflow_relay.exceptions import ConfigurationError


class TestValidateMemflowApiKey:
    def test_valid_key(self):
        validate_memflow_api_key("lago_abc12345")  # should not raise

    def test_valid_key_with_dashes(self):
        validate_memflow_api_key("lago_abc-def-1234")

    def test_valid_key_with_underscores(self):
        validate_memflow_api_key("lago_abc_def_1234567890")

    def test_none_raises(self):
        with pytest.raises(ConfigurationError):
            validate_memflow_api_key(None)

    def test_empty_raises(self):
        with pytest.raises(ConfigurationError):
            validate_memflow_api_key("")

    def test_no_prefix_raises(self):
        with pytest.raises(ConfigurationError):
            validate_memflow_api_key("abc12345678")

    def test_too_short_suffix_raises(self):
        with pytest.raises(ConfigurationError):
            validate_memflow_api_key("lago_short")  # only 5 chars after prefix

    def test_whitespace_raises(self):
        with pytest.raises(ConfigurationError):
            validate_memflow_api_key("   ")


class TestIsValidMemflowKey:
    def test_valid(self):
        assert is_valid_memflow_key("lago_validkey123") is True

    def test_none(self):
        assert is_valid_memflow_key(None) is False

    def test_invalid_prefix(self):
        assert is_valid_memflow_key("sk_validkey12345") is False


class TestMemflowAuthHeaders:
    def test_returns_authorization_header(self):
        headers = memflow_auth_headers("lago_abc12345678")
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer lago_")

    def test_no_gemini_in_headers(self):
        headers = memflow_auth_headers("lago_abc12345678")
        header_str = str(headers).lower()
        assert "gemini" not in header_str
        assert "goog" not in header_str

    def test_client_header_present(self):
        headers = memflow_auth_headers("lago_abc12345678")
        assert "X-MemFlow-Client" in headers
