"""Local HTTP proxy server for MemFlow Relay.

Listens on 127.0.0.1:{MEMFLOW_PORT} and proxies requests to Gemini,
applying shadow / safe / optimize mode dispatch.

Mode dispatch:
  shadow   — forward original request unchanged (invariant: original == sent).
  safe     — call optimizer; if decision==bypass or any error, forward original.
  optimize — call optimizer; if fail_open and error, forward original.

Credential boundary enforced here:
  - GEMINI_API_KEY injected by GeminiProvider only.
  - Body sent to optimizer has GEMINI_API_KEY stripped.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib.parse import unquote

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from memflow_relay.config import RelayConfig, RelayMode
from memflow_relay.optimizer import MemFlowOptimizer, bypass_result
from memflow_relay.providers.gemini import GeminiProvider
from memflow_relay.security.redaction import redact_headers
from memflow_relay.stats import RelayStats

logger = logging.getLogger(__name__)


def _strip_gemini_key(body: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *body* with any gemini API key fields removed.

    This is a defensive strip applied before sending any body to the
    MemFlow optimizer. GEMINI_API_KEY must never leave the local machine.
    """
    return {k: v for k, v in body.items() if "gemini" not in k.lower() and "goog" not in k.lower()}


def _strip_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    """Strip provider credentials and hop-by-hop headers from upstream headers."""
    skip = {"x-goog-api-key", "authorization", "host"}
    return {k: v for k, v in headers.items() if k.lower() not in skip}


def build_app(config: RelayConfig, stats: RelayStats) -> Starlette:
    """Create and return the Starlette ASGI application."""

    provider = GeminiProvider(
        api_key=config.gemini_api_key,
        base_url=config.gemini_api_base_url,
    )

    optimizer = MemFlowOptimizer(
        api_key=config.memflow_api_key,
        api_url=config.memflow_api_url,
        timeout=config.optimizer_timeout_seconds,
        fail_open=config.memflow_fail_open,
    )

    async def proxy_handler(request: Request) -> Response:
        t_start = time.monotonic()
        # Decode percent-encoded characters in the path so that colons in model
        # names (e.g. gemini-3.8-flash:generateContent) are forwarded correctly
        # to the Gemini API. Uvicorn stores the raw path in scope["raw_path"]
        # and the decoded path in scope["path"], but Starlette's request.url.path
        # may re-encode it. Use scope["path"] with an explicit unquote to be safe.
        path = unquote(request.scope.get("path", request.url.path))
        query = str(request.url.query)
        if query:
            path = f"{path}?{query}"

        raw_body = await request.body()
        try:
            original_body: dict[str, Any] = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            original_body = {}

        incoming_headers = _strip_sensitive_headers(dict(request.headers))
        stream = "stream" in str(original_body.get("generationConfig", {})) or (
            request.headers.get("accept", "") == "text/event-stream"
        )

        mode = config.memflow_mode

        # ── SHADOW MODE ─────────────────────────────────────────────────────
        if mode is RelayMode.shadow:
            logger.debug(
                "shadow mode — forwarding original request to Gemini | headers=%s",
                redact_headers(incoming_headers),
            )
            result = await provider.forward(path, original_body, incoming_headers, stream=stream)
            stats.record_bypass()
            return _make_response(result, stream=stream)

        # ── SAFE / OPTIMIZE MODE ─────────────────────────────────────────────
        body_for_optimizer = _strip_gemini_key(original_body)
        opt_result = await optimizer.analyze(body_for_optimizer, mode=mode.value)

        latency_ms = (time.monotonic() - t_start) * 1000

        if opt_result.should_optimize and mode is not RelayMode.shadow:
            optimized_body = opt_result.optimized_body
            logger.debug(
                "optimize — forwarding optimized request to Gemini (tokens_saved=%d)",
                opt_result.tokens_saved,
            )
            result = await provider.forward(path, optimized_body, incoming_headers, stream=stream)
            stats.record_optimized(tokens_saved=opt_result.tokens_saved, latency_ms=latency_ms)
        else:
            logger.debug(
                "bypass — forwarding original request to Gemini (reason=%s)",
                opt_result.reason,
            )
            result = await provider.forward(path, original_body, incoming_headers, stream=stream)
            if opt_result.decision == "bypass" and mode is RelayMode.safe:
                stats.record_analyzed_bypass(latency_ms=latency_ms)
            else:
                stats.record_bypass()

        return _make_response(result, stream=stream)

    async def health_handler(_request: Request) -> Response:
        return Response(content='{"status":"ok"}', media_type="application/json")

    # Starlette Route("/{path:path}") does not match paths containing colons
    # (e.g. /v1beta/models/gemini-2.5-flash:generateContent) because colons
    # are treated as route parameter separators. Use a custom ASGI middleware
    # approach: route /_health explicitly, pass everything else to proxy_handler.

    starlette_app = Starlette(routes=[
        Route("/_health", health_handler, methods=["GET"]),
    ])

    async def root_app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path", "") == "/_health":
            await starlette_app(scope, receive, send)
        elif scope["type"] == "http":
            request = Request(scope, receive, send)
            response = await proxy_handler(request)
            await response(scope, receive, send)
        else:
            await starlette_app(scope, receive, send)

    return root_app  # type: ignore[return-value]


def _make_response(
    result: tuple,
    *,
    stream: bool = False,
) -> Response:
    status_code, resp_headers, body_or_iter = result
    # Filter hop-by-hop headers
    skip = {"transfer-encoding", "connection", "keep-alive"}
    headers = {k: v for k, v in resp_headers.items() if k.lower() not in skip}

    if stream:
        async def _aiter():
            async for chunk in body_or_iter:
                yield chunk

        return StreamingResponse(
            _aiter(),
            status_code=status_code,
            headers=headers,
            media_type="text/event-stream",
        )

    return Response(
        content=body_or_iter,
        status_code=status_code,
        headers=headers,
    )
