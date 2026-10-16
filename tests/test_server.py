"""Server integration tests.

Critical invariants verified:
1. Shadow mode invariant: request_sent_to_gemini == original_request
2. Fail-open: optimizer failure → original request forwarded, server returns 200
3. Credential isolation: GEMINI_API_KEY never sent to optimizer endpoint
4. Safe mode bypass: optimizer says bypass → original request forwarded
5. Optimize mode: optimizer says optimize → optimized body forwarded
"""
from __future__ import annotations

import json

import httpx
import pytest
import respx
from starlette.testclient import TestClient

from memflow_relay.config import RelayConfig, RelayMode
from memflow_relay.server import build_app
from memflow_relay.stats import RelayStats

GEMINI_BASE = "https://generativelanguage.googleapis.com"
OPTIMIZER_URL = "https://api.lamoonagi.com"
GEMINI_KEY = "AIzaSyFakeGeminiKey123456789"
MEMFLOW_KEY = "lago_testkey1234567890abcde"

ORIGINAL_BODY = {
    "contents": [{"parts": [{"text": "What is the capital of France?"}]}]
}
OPTIMIZED_BODY = {
    "contents": [{"parts": [{"text": "Capital of France?"}]}]
}
GEMINI_RESPONSE = {
    "candidates": [{"content": {"parts": [{"text": "Paris"}]}}],
    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 1, "totalTokenCount": 11},
}


def _make_config(**kwargs) -> RelayConfig:
    defaults = dict(
        gemini_api_key=GEMINI_KEY,
        memflow_api_key=MEMFLOW_KEY,
        gemini_api_base_url=GEMINI_BASE,
        memflow_api_url=OPTIMIZER_URL,
        memflow_fail_open=True,
    )
    defaults.update(kwargs)
    return RelayConfig(**defaults)


def _make_app(config: RelayConfig) -> TestClient:
    stats = RelayStats()
    app = build_app(config, stats)
    return TestClient(app, raise_server_exceptions=True)


# ── Shadow mode invariant ─────────────────────────────────────────────────────


class TestShadowModeInvariant:
    """In shadow mode, the request forwarded to Gemini must match the original."""

    @respx.mock
    def test_shadow_forwards_original_body(self):
        captured_body: dict = {}

        def capture(request: httpx.Request):
            nonlocal captured_body
            captured_body = json.loads(request.content)
            return httpx.Response(200, json=GEMINI_RESPONSE)

        # Mock Gemini endpoint
        respx.post(f"{GEMINI_BASE}/v1beta/models/gemini-1.5-pro:generateContent").mock(
            side_effect=capture
        )

        config = _make_config(memflow_mode="shadow")
        client = _make_app(config)

        resp = client.post(
            "/v1beta/models/gemini-1.5-pro:generateContent",
            json=ORIGINAL_BODY,
        )
        assert resp.status_code == 200
        # THE SHADOW INVARIANT: body sent to Gemini == original body
        assert captured_body == ORIGINAL_BODY, (
            "Shadow mode invariant violated: body sent to Gemini differs from original request."
        )

    @respx.mock
    def test_shadow_does_not_call_optimizer(self):
        optimizer_called = False

        def optimizer_spy(request: httpx.Request):
            nonlocal optimizer_called
            optimizer_called = True
            return httpx.Response(200, json={"decision": "bypass"})

        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(side_effect=optimizer_spy)
        respx.post(f"{GEMINI_BASE}/v1beta/models/gemini-1.5-pro:generateContent").mock(
            return_value=httpx.Response(200, json=GEMINI_RESPONSE)
        )

        config = _make_config(memflow_mode="shadow")
        client = _make_app(config)
        client.post("/v1beta/models/gemini-1.5-pro:generateContent", json=ORIGINAL_BODY)

        assert optimizer_called is False, (
            "Shadow mode must NEVER call the MemFlow optimizer."
        )


# ── Fail-open invariant ───────────────────────────────────────────────────────


class TestFailOpen:
    """When optimizer fails, original request must be forwarded and response returned."""

    @respx.mock
    def test_optimizer_timeout_forwards_original(self):
        captured_body: dict = {}

        def gemini_capture(request: httpx.Request):
            nonlocal captured_body
            captured_body = json.loads(request.content)
            return httpx.Response(200, json=GEMINI_RESPONSE)

        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        respx.post(f"{GEMINI_BASE}/v1beta/models/gemini-1.5-pro:generateContent").mock(
            side_effect=gemini_capture
        )

        config = _make_config(memflow_mode="optimize", memflow_fail_open=True)
        client = _make_app(config)
        resp = client.post(
            "/v1beta/models/gemini-1.5-pro:generateContent", json=ORIGINAL_BODY
        )

        assert resp.status_code == 200
        assert captured_body == ORIGINAL_BODY, (
            "Fail-open violated: original body was not forwarded after optimizer timeout."
        )

    @respx.mock
    def test_optimizer_500_forwards_original(self):
        captured_body: dict = {}

        def gemini_capture(request: httpx.Request):
            nonlocal captured_body
            captured_body = json.loads(request.content)
            return httpx.Response(200, json=GEMINI_RESPONSE)

        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        respx.post(f"{GEMINI_BASE}/v1beta/models/gemini-1.5-pro:generateContent").mock(
            side_effect=gemini_capture
        )

        config = _make_config(memflow_mode="safe", memflow_fail_open=True)
        client = _make_app(config)
        resp = client.post(
            "/v1beta/models/gemini-1.5-pro:generateContent", json=ORIGINAL_BODY
        )

        assert resp.status_code == 200
        assert captured_body == ORIGINAL_BODY

    @respx.mock
    def test_optimizer_connection_error_forwards_original(self):
        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            side_effect=httpx.ConnectError("refused")
        )
        respx.post(f"{GEMINI_BASE}/v1beta/models/gemini-1.5-pro:generateContent").mock(
            return_value=httpx.Response(200, json=GEMINI_RESPONSE)
        )

        config = _make_config(memflow_mode="optimize", memflow_fail_open=True)
        client = _make_app(config)
        resp = client.post(
            "/v1beta/models/gemini-1.5-pro:generateContent", json=ORIGINAL_BODY
        )
        assert resp.status_code == 200


# ── Credential isolation in server ───────────────────────────────────────────


class TestServerCredentialIsolation:
    """GEMINI_API_KEY must not appear in any request to the optimizer."""

    @respx.mock
    def test_gemini_key_not_in_optimizer_request(self):
        captured_optimizer_req: httpx.Request | None = None

        def capture_opt(request: httpx.Request):
            nonlocal captured_optimizer_req
            captured_optimizer_req = request
            return httpx.Response(200, json={"decision": "bypass"})

        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(side_effect=capture_opt)
        respx.post(f"{GEMINI_BASE}/v1beta/models/gemini-1.5-pro:generateContent").mock(
            return_value=httpx.Response(200, json=GEMINI_RESPONSE)
        )

        config = _make_config(memflow_mode="safe")
        client = _make_app(config)
        client.post("/v1beta/models/gemini-1.5-pro:generateContent", json=ORIGINAL_BODY)

        assert captured_optimizer_req is not None
        req_str = (
            str(captured_optimizer_req.headers).lower()
            + captured_optimizer_req.content.decode("utf-8", errors="replace").lower()
        )
        assert GEMINI_KEY.lower() not in req_str, (
            "GEMINI_API_KEY must never be sent to the MemFlow optimizer."
        )
        assert "aizas" not in req_str, (
            "Google API key signature (AIzaS...) must not appear in optimizer request."
        )

    @respx.mock
    def test_gemini_key_injected_only_in_gemini_request(self):
        captured_gemini_req: httpx.Request | None = None

        def capture_gemini(request: httpx.Request):
            nonlocal captured_gemini_req
            captured_gemini_req = request
            return httpx.Response(200, json=GEMINI_RESPONSE)

        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            return_value=httpx.Response(200, json={"decision": "bypass"})
        )
        respx.post(f"{GEMINI_BASE}/v1beta/models/gemini-1.5-pro:generateContent").mock(
            side_effect=capture_gemini
        )

        config = _make_config(memflow_mode="safe")
        client = _make_app(config)
        client.post("/v1beta/models/gemini-1.5-pro:generateContent", json=ORIGINAL_BODY)

        assert captured_gemini_req is not None
        gemini_headers = dict(captured_gemini_req.headers)
        assert "x-goog-api-key" in gemini_headers, (
            "GEMINI_API_KEY must be injected into Gemini requests via x-goog-api-key."
        )
        assert gemini_headers["x-goog-api-key"] == GEMINI_KEY


# ── Safe mode ─────────────────────────────────────────────────────────────────


class TestSafeMode:
    @respx.mock
    def test_safe_mode_bypass_forwards_original(self):
        captured_body: dict = {}

        def gemini_capture(request: httpx.Request):
            nonlocal captured_body
            captured_body = json.loads(request.content)
            return httpx.Response(200, json=GEMINI_RESPONSE)

        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            return_value=httpx.Response(200, json={"decision": "bypass", "reason": "optimal"})
        )
        respx.post(f"{GEMINI_BASE}/v1beta/models/gemini-1.5-pro:generateContent").mock(
            side_effect=gemini_capture
        )

        config = _make_config(memflow_mode="safe")
        client = _make_app(config)
        client.post("/v1beta/models/gemini-1.5-pro:generateContent", json=ORIGINAL_BODY)

        assert captured_body == ORIGINAL_BODY

    @respx.mock
    def test_safe_mode_optimize_forwards_optimized_body(self):
        captured_body: dict = {}

        def gemini_capture(request: httpx.Request):
            nonlocal captured_body
            captured_body = json.loads(request.content)
            return httpx.Response(200, json=GEMINI_RESPONSE)

        respx.post(f"{OPTIMIZER_URL}/v1/context/optimize").mock(
            return_value=httpx.Response(
                200,
                json={
                    "decision": "optimize",
                    "optimized_body": OPTIMIZED_BODY,
                    "tokens_saved": 5,
                },
            )
        )
        respx.post(f"{GEMINI_BASE}/v1beta/models/gemini-1.5-pro:generateContent").mock(
            side_effect=gemini_capture
        )

        config = _make_config(memflow_mode="safe")
        client = _make_app(config)
        resp = client.post(
            "/v1beta/models/gemini-1.5-pro:generateContent", json=ORIGINAL_BODY
        )

        assert resp.status_code == 200
        assert captured_body == OPTIMIZED_BODY


# ── Health endpoint ───────────────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        config = _make_config(memflow_mode="shadow")
        client = _make_app(config)
        resp = client.get("/_health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
