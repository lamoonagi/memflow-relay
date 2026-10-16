"""Custom exception hierarchy for MemFlow Relay."""

from __future__ import annotations


class MemFlowRelayError(Exception):
    """Base exception for all MemFlow Relay errors."""


class ConfigurationError(MemFlowRelayError):
    """Raised when required configuration is missing or invalid."""


class AuthError(MemFlowRelayError):
    """Raised for authentication or authorization failures."""


class OptimizerError(MemFlowRelayError):
    """Raised when the MemFlow optimizer call fails."""


class OptimizerTimeoutError(OptimizerError):
    """Raised when the optimizer request times out."""


class GeminiError(MemFlowRelayError):
    """Raised when the Gemini upstream returns an error."""


class RedactionError(MemFlowRelayError):
    """Raised when secret redaction itself encounters an unexpected error."""
