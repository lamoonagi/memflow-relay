"""Tests for the optimizer module.

Covers:
- Fail-open invariant: when optimizer raises/times out, bypass is returned
  and the caller receives a valid OptimizationResult with decision=bypass.
- Credential isolation: GEMINI_API_KEY never reaches the optimizer endpoint.
- No-key bypass: no MEMFLOW_API_KEY → immediate bypass.
"""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from memflow_relay.optimizer import MemFlowOptimizer, bypass_result


OPTIMIZER_URL = "https://api.lamoonagi.com"
MEMFLOW_KEY = "lago_testkey1234567890abcde"
SAMPLE_BODY = {"contents": [{"parts": [{"text": "Hello"}]}]}


class TestBypassResult:
    def test_bypass_result_decision(self):
        r = bypass_result("fail_open")
        assert r.decision == "bypass"
        assert r.should_optimize is False

    def test_bypass_result_unknown_key(self):
        r = bypass_result("some_custom_reason")
        assert r.decision == "bypass"


class TestOptimizerNoKey:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_bypass(self):
        opt = MemFlowOptimizer(api_key=None, api_url=OPTIMIZER_URL, fail_open=True)
        result = await opt.analyze(SAMPLE_BODY)
        assert result.decision == "bypass"
        assert result.should_optimize is False


class TestOptimizerFailOpen:
    """Fail-open invariant: optimizer errors → bypass, never raise."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_returns_bypass(self):
        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        opt = MemFlowOptimizer(
            api_key=MEMFLOW_KEY, api_url=OPTIMIZER_URL, fail_open=True, timeout=1.0
        )
        result = await opt.analyze(SAMPLE_BODY)
        assert result.decision == "bypass"
        assert result.should_optimize is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error_returns_bypass(self):
        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        opt = MemFlowOptimizer(
            api_key=MEMFLOW_KEY, api_url=OPTIMIZER_URL, fail_open=True
        )
        result = await opt.analyze(SAMPLE_BODY)
        assert result.decision == "bypass"

    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_error_returns_bypass(self):
        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        opt = MemFlowOptimizer(
            api_key=MEMFLOW_KEY, api_url=OPTIMIZER_URL, fail_open=True
        )
        result = await opt.analyze(SAMPLE_BODY)
        assert result.decision == "bypass"


class TestOptimizerFailClosed:
    """When fail_open=False, errors should propagate."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_raises_when_fail_closed(self):
        from memflow_relay.exceptions import OptimizerTimeoutError
        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        opt = MemFlowOptimizer(
            api_key=MEMFLOW_KEY, api_url=OPTIMIZER_URL, fail_open=False, timeout=1.0
        )
        with pytest.raises(OptimizerTimeoutError):
            await opt.analyze(SAMPLE_BODY)

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error_raises_when_fail_closed(self):
        from memflow_relay.exceptions import OptimizerError
        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )
        opt = MemFlowOptimizer(
            api_key=MEMFLOW_KEY, api_url=OPTIMIZER_URL, fail_open=False
        )
        with pytest.raises(OptimizerError):
            await opt.analyze(SAMPLE_BODY)


class TestOptimizerOptimizeDecision:
    @pytest.mark.asyncio
    @respx.mock
    async def test_optimize_decision_returned(self):
        optimized = {"contents": [{"parts": [{"text": "Optimized!"}]}]}
        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            return_value=httpx.Response(
                200,
                json={
                    "decision": "optimize",
                    "optimized_body": optimized,
                    "tokens_saved": 42,
                    "reason": "context_compressed",
                },
            )
        )
        opt = MemFlowOptimizer(api_key=MEMFLOW_KEY, api_url=OPTIMIZER_URL, fail_open=True)
        result = await opt.analyze(SAMPLE_BODY)
        assert result.decision == "optimize"
        assert result.should_optimize is True
        assert result.tokens_saved == 42
        assert result.optimized_body == optimized

    @pytest.mark.asyncio
    @respx.mock
    async def test_bypass_decision_returned(self):
        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            return_value=httpx.Response(
                200,
                json={"decision": "bypass", "reason": "already_optimal"},
            )
        )
        opt = MemFlowOptimizer(api_key=MEMFLOW_KEY, api_url=OPTIMIZER_URL, fail_open=True)
        result = await opt.analyze(SAMPLE_BODY)
        assert result.decision == "bypass"
        assert result.should_optimize is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_unknown_decision_defaults_to_bypass(self):
        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            return_value=httpx.Response(200, json={"decision": "unknown_value"})
        )
        opt = MemFlowOptimizer(api_key=MEMFLOW_KEY, api_url=OPTIMIZER_URL, fail_open=True)
        result = await opt.analyze(SAMPLE_BODY)
        assert result.decision == "bypass"


class TestCredentialIsolation:
    """GEMINI_API_KEY must NEVER be sent to the MemFlow optimizer."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_gemini_key_not_in_optimizer_request(self):
        """Verify the optimizer does not receive GEMINI_API_KEY in its headers.

        Stripping Gemini fields from the *body* is the server's responsibility
        (server.py/_strip_gemini_key). The optimizer receives the already-stripped
        body from the server. This test verifies the optimizer's own headers never
        contain Gemini credentials.
        """
        captured_headers: dict = {}

        def capture(request: httpx.Request):
            nonlocal captured_headers
            captured_headers = dict(request.headers)
            return httpx.Response(200, json={"decision": "bypass"})

        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(side_effect=capture)

        opt = MemFlowOptimizer(api_key=MEMFLOW_KEY, api_url=OPTIMIZER_URL, fail_open=True)
        await opt.analyze(SAMPLE_BODY)

        # The optimizer request headers must contain MEMFLOW_API_KEY, not Gemini key
        header_str = str(captured_headers).lower()
        assert "gemini" not in header_str, (
            "GEMINI_API_KEY must never appear in optimizer request headers."
        )
        assert "aizasy" not in header_str, (
            "Google API key signature must not appear in optimizer request headers."
        )
        assert "lago_" in str(captured_headers), (
            "MEMFLOW_API_KEY (lago_...) must be present in optimizer request."
        )

    @pytest.mark.asyncio
    @respx.mock
    async def test_gemini_key_not_in_optimizer_headers(self):
        """Verify Authorization header contains only MEMFLOW_API_KEY."""
        captured_headers: dict = {}

        def capture(request: httpx.Request):
            nonlocal captured_headers
            captured_headers = dict(request.headers)
            return httpx.Response(200, json={"decision": "bypass"})

        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(side_effect=capture)

        opt = MemFlowOptimizer(api_key=MEMFLOW_KEY, api_url=OPTIMIZER_URL, fail_open=True)
        await opt.analyze(SAMPLE_BODY)

        auth = captured_headers.get("authorization", "")
        assert MEMFLOW_KEY in auth or auth.startswith("Bearer lago_"), (
            "Authorization header must use MEMFLOW_API_KEY."
        )
        assert "gemini" not in str(captured_headers).lower(), (
            "GEMINI_API_KEY must never appear in optimizer request headers."
        )
        assert "goog" not in str(captured_headers).lower(), (
            "Google credentials must never appear in optimizer request headers."
        )
