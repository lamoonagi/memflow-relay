"""MemFlow optimizer client.

Calls the LamoonAGI context optimizer API to decide whether a request
should be optimized and, if so, returns an optimized payload.

Credential boundary:
- MEMFLOW_API_KEY is sent to api.lamoonagi.com.
- GEMINI_API_KEY is NEVER included in optimizer requests.

Fail-open guarantee:
- If the optimizer is unreachable, times out, or returns an unexpected
  response, and ``fail_open=True`` (default), the caller receives a
  ``bypass`` decision and the original request is forwarded unchanged.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

from memflow_relay.auth import memflow_auth_headers
from memflow_relay.exceptions import OptimizerError, OptimizerTimeoutError
from memflow_relay.security.redaction import redact

logger = logging.getLogger(__name__)

OptimizerDecision = Literal["optimize", "bypass"]

_BYPASS_REASONS = {
    "fail_open": "optimizer unavailable — fail-open applied",
    "timeout": "optimizer timed out — fail-open applied",
    "error": "optimizer error — fail-open applied",
    "shadow_mode": "shadow mode — optimization skipped",
    "no_key": "MEMFLOW_API_KEY not configured",
    "optimizer_decision": "optimizer decided bypass",
}


class OptimizationResult:
    """Result from the MemFlow optimizer."""

    __slots__ = ("decision", "reason", "optimized_body", "tokens_saved")

    def __init__(
        self,
        *,
        decision: OptimizerDecision,
        reason: str = "",
        optimized_body: dict[str, Any] | None = None,
        tokens_saved: int = 0,
    ) -> None:
        self.decision = decision
        self.reason = reason
        self.optimized_body = optimized_body
        self.tokens_saved = tokens_saved

    @property
    def should_optimize(self) -> bool:
        return self.decision == "optimize" and self.optimized_body is not None


def bypass_result(reason_key: str) -> OptimizationResult:
    """Construct a standardized bypass result."""
    return OptimizationResult(
        decision="bypass",
        reason=_BYPASS_REASONS.get(reason_key, reason_key),
    )


class MemFlowOptimizer:
    """Calls the LamoonAGI optimizer endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None,
        api_url: str,
        timeout: float = 3.0,
        fail_open: bool = True,
    ) -> None:
        self._api_key = api_key
        self._api_url = api_url.rstrip("/")
        self._timeout = timeout
        self._fail_open = fail_open

    async def analyze(
        self,
        request_body: dict[str, Any],
        *,
        mode: str = "safe",
    ) -> OptimizationResult:
        """Ask the optimizer whether *request_body* should be optimized.

        Returns an :class:`OptimizationResult` with ``decision`` set to
        ``"optimize"`` or ``"bypass"``.

        IMPORTANT: *request_body* must never contain GEMINI_API_KEY.
        The caller is responsible for stripping provider credentials before
        passing the body here.
        """
        if not self._api_key:
            return bypass_result("no_key")

        headers = memflow_auth_headers(self._api_key)
        # Explicitly confirm GEMINI_API_KEY is not in headers (safety assertion).
        assert "gemini" not in str(headers).lower(), (
            "BUG: Gemini credentials must never appear in optimizer headers."
        )

        payload: dict[str, Any] = {
            "mode": mode,
            "body": request_body,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._api_url}/v1/context/optimize",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            if self._fail_open:
                logger.warning("optimizer timeout — fail-open: %s", redact(str(exc)))
                return bypass_result("timeout")
            raise OptimizerTimeoutError("MemFlow optimizer timed out") from exc
        except httpx.HTTPError as exc:
            if self._fail_open:
                logger.warning("optimizer error — fail-open: %s", redact(str(exc)))
                return bypass_result("fail_open")
            raise OptimizerError(f"MemFlow optimizer HTTP error: {redact(str(exc))}") from exc
        except Exception as exc:  # noqa: BLE001
            if self._fail_open:
                logger.warning("optimizer unexpected error — fail-open: %s", redact(str(exc)))
                return bypass_result("error")
            raise OptimizerError(f"MemFlow optimizer error: {redact(str(exc))}") from exc

        decision: OptimizerDecision = data.get("decision", "bypass")
        if decision not in ("optimize", "bypass"):
            decision = "bypass"

        if decision == "optimize":
            optimized_body = data.get("optimized_body")
            tokens_saved = int(data.get("tokens_saved", 0))
            return OptimizationResult(
                decision="optimize",
                reason=data.get("reason", ""),
                optimized_body=optimized_body,
                tokens_saved=tokens_saved,
            )

        return OptimizationResult(
            decision="bypass",
            reason=data.get("reason", _BYPASS_REASONS["optimizer_decision"]),
        )
