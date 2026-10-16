"""Authentication helpers for MemFlow Relay.

Validates MEMFLOW_API_KEY format and generates request headers for
LamoonAGI optimizer API calls. GEMINI_API_KEY is handled separately
by the Gemini provider and is never passed through this module.
"""

from __future__ import annotations

import re

from memflow_relay.exceptions import ConfigurationError
from memflow_relay.security.redaction import register_secret

# lago_ prefix followed by at least 8 alphanumeric/dash/underscore characters.
_MEMFLOW_KEY_RE = re.compile(r"^lago_[A-Za-z0-9_\-]{8,}$", re.ASCII)


def validate_memflow_api_key(key: str | None) -> None:
    """Raise :exc:`ConfigurationError` if *key* does not look like a valid MemFlow API key.

    Valid format: ``lago_`` followed by ≥ 8 alphanumeric/dash/underscore characters.
    """
    if key is None or key.strip() == "":
        raise ConfigurationError(
            "MEMFLOW_API_KEY is not set. "
            "Set it to your LamoonAGI API key (lago_...) to use optimize or safe modes."
        )
    if not _MEMFLOW_KEY_RE.match(key):
        raise ConfigurationError(
            "MEMFLOW_API_KEY format is invalid. "
            "Expected format: lago_<alphanumeric+dash+underscore, min 8 chars>."
        )


def memflow_auth_headers(key: str) -> dict[str, str]:
    """Return HTTP headers for authenticating requests to the MemFlow optimizer API.

    The returned headers contain only the MemFlow API key.
    GEMINI_API_KEY is never included here.
    """
    # Register for redaction whenever we build a header — cheap, idempotent.
    register_secret(key)
    return {
        "Authorization": f"Bearer {key}",
        "X-MemFlow-Client": "memflow-relay/0.1.0",
    }


def is_valid_memflow_key(key: str | None) -> bool:
    """Return True if *key* passes format validation."""
    if key is None:
        return False
    return bool(_MEMFLOW_KEY_RE.match(key))
