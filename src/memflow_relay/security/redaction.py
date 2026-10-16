"""Centralized secret redaction for MemFlow Relay.

Any string that passes through logs, exception messages, or telemetry
MUST be processed by :func:`redact` before being written or transmitted.

Patterns redacted:
- GEMINI_API_KEY environment variable value
- MEMFLOW_API_KEY environment variable value (lago_* prefix)
- Bare lago_* tokens appearing in text
- Authorization / Bearer tokens
- Cookie header values
- Generic "secret", "password", "api_key" key=value pairs
"""

from __future__ import annotations

import re

# ── Pattern registry ──────────────────────────────────────────────────────────

# lago_ prefixed keys (MemFlow API keys)
_LAGO_TOKEN_RE = re.compile(r"lago_[A-Za-z0-9_\-]{8,}", re.ASCII)

# Bearer tokens in Authorization headers
_BEARER_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.=+/]{8,}")

# "Authorization: <value>" header lines
_AUTH_HEADER_RE = re.compile(r"(?i)(authorization:\s*)\S+")

# Cookie header values
_COOKIE_HEADER_RE = re.compile(r"(?i)(cookie:\s*).*")

# key=value / key: value patterns for sensitive names
_KV_SENSITIVE_RE = re.compile(
    r'(?i)((?:api[_\-]?key|secret|password|token|credential)["\s]*[=:]\s*)["\']?[A-Za-z0-9_\-\.=+/]{4,}["\']?'
)

# Standalone long random-looking tokens (40+ hex or base64 chars)
_GENERIC_SECRET_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9+/]{40,}={0,2}(?![A-Za-z0-9])")

_REPLACEMENT = "[REDACTED]"

# Runtime-registered literal secrets (populated by auth.py on startup)
_runtime_secrets: list[str] = []


def register_secret(value: str) -> None:
    """Register a literal secret value to be redacted from all output.

    Call this once during startup for each credential loaded from env vars.
    """
    if value and value not in _runtime_secrets:
        _runtime_secrets.append(value)


def _clear_runtime_secrets() -> None:
    """Clear runtime secrets — used in tests only."""
    _runtime_secrets.clear()


def redact(text: str) -> str:
    """Return *text* with all recognized secret patterns replaced by ``[REDACTED]``.

    This is a pure function with no side-effects; it never raises.
    """
    if not text:
        return text

    # Literal runtime-registered secrets first (exact string match)
    for secret in _runtime_secrets:
        if secret and secret in text:
            text = text.replace(secret, _REPLACEMENT)

    # Regex patterns (most-specific first to avoid double-replacement)
    text = _LAGO_TOKEN_RE.sub(_REPLACEMENT, text)
    text = _BEARER_RE.sub(r"\g<1>" + _REPLACEMENT, text)
    text = _AUTH_HEADER_RE.sub(r"\g<1>" + _REPLACEMENT, text)
    text = _COOKIE_HEADER_RE.sub(r"\g<1>" + _REPLACEMENT, text)
    text = _KV_SENSITIVE_RE.sub(r"\g<1>" + _REPLACEMENT, text)

    return text


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of *headers* with sensitive values replaced.

    Safe to pass directly to loggers or telemetry payloads.
    """
    sensitive_keys = {"authorization", "cookie", "x-api-key", "x-goog-api-key"}
    return {
        k: (_REPLACEMENT if k.lower() in sensitive_keys else v)
        for k, v in headers.items()
    }
