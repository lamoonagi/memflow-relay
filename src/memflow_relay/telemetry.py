"""Telemetry for MemFlow Relay.

Three modes:
- off          — nothing transmitted.
- metrics_only — aggregate counts and token-size buckets; NO raw prompt content.
- diagnostic   — adds anonymized request-structure metadata; still no raw prompts.

All telemetry payloads are assembled here and pass through redaction before
being dispatched. Prompt content is structurally excluded (never added, not
redacted-after-the-fact) in metrics_only and diagnostic modes.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from memflow_relay.config import TelemetryMode
from memflow_relay.security.redaction import redact

logger = logging.getLogger(__name__)

# Token-size bucket boundaries (number of estimated tokens)
_TOKEN_BUCKETS = [0, 100, 500, 1_000, 5_000, 10_000, 50_000, 100_000]


def _token_bucket(token_count: int) -> str:
    """Return a string bucket label for *token_count*."""
    for boundary in reversed(_TOKEN_BUCKETS):
        if token_count >= boundary:
            return f">={boundary}"
    return "<0"


class TelemetryDispatcher:
    """Collects and dispatches telemetry events based on the configured mode."""

    def __init__(self, mode: TelemetryMode) -> None:
        self._mode = mode

    @property
    def mode(self) -> TelemetryMode:
        return self._mode

    def record_request(
        self,
        *,
        decision: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        latency_ms: float,
        optimizer_called: bool,
        relay_mode: str,
        # NOTE: prompt_content is intentionally NOT a parameter here.
        # Structural exclusion, not post-hoc redaction.
    ) -> None:
        """Record a completed relay request event."""
        if self._mode is TelemetryMode.off:
            return

        payload: dict[str, Any] = {
            "event": "relay.request",
            "ts": time.time(),
            "relay_mode": relay_mode,
            "decision": decision,
            "optimizer_called": optimizer_called,
            "input_token_bucket": _token_bucket(estimated_input_tokens),
            "output_token_bucket": _token_bucket(estimated_output_tokens),
            "latency_ms": round(latency_ms, 1),
        }

        # diagnostic adds request-structure info but still no prompt content
        if self._mode is TelemetryMode.diagnostic:
            payload["diagnostic"] = True

        self._dispatch(payload)

    def record_error(self, *, error_type: str, relay_mode: str) -> None:
        """Record an error event (no message content)."""
        if self._mode is TelemetryMode.off:
            return
        payload: dict[str, Any] = {
            "event": "relay.error",
            "ts": time.time(),
            "relay_mode": relay_mode,
            "error_type": error_type,
        }
        self._dispatch(payload)

    def _dispatch(self, payload: dict[str, Any]) -> None:
        """Dispatch a telemetry payload.

        In this implementation we log at DEBUG level after redaction.
        A production build would batch-send to the LamoonAGI telemetry endpoint.
        """
        # Redact the string representation before logging
        safe_repr = redact(str(payload))
        logger.debug("telemetry: %s", safe_repr)
