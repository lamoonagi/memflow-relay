"""Gemini API provider adapter.

Forwards requests to generativelanguage.googleapis.com using
GEMINI_API_KEY. This key is NEVER forwarded to LamoonAGI.

Supports:
- Non-streaming responses (full body returned as bytes).
- Streaming responses (SSE / chunked, proxied as an async byte iterator).
- Usage metric extraction from response bodies.
- Connectivity health check.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import httpx

from memflow_relay.exceptions import ConfigurationError, GeminiError
from memflow_relay.providers.base import BaseProvider
from memflow_relay.security.redaction import register_secret

logger = logging.getLogger(__name__)

_GEMINI_BASE = "https://generativelanguage.googleapis.com"


class GeminiProvider(BaseProvider):
    """Sends requests to the Gemini API."""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = _GEMINI_BASE,
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY is not set. "
                "It is required for the Gemini provider."
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        # Register Gemini key for redaction in logs.
        # It is never sent to LamoonAGI.
        register_secret(api_key)

    def _gemini_url(self, path: str) -> str:
        path = path.lstrip("/")
        return f"{self._base_url}/{path}"

    def _inject_api_key(self, headers: dict[str, str]) -> dict[str, str]:
        """Return headers with the Gemini API key added.

        Only used for Gemini upstream requests.
        """
        merged = dict(headers)
        merged["x-goog-api-key"] = self._api_key  # type: ignore[assignment]
        return merged

    async def forward(
        self,
        path: str,
        body: dict[str, Any],
        headers: dict[str, str],
        *,
        stream: bool = False,
    ) -> tuple[int, dict[str, str], bytes | AsyncIterator[bytes]]:
        """Forward *body* to the Gemini endpoint."""
        url = self._gemini_url(path)
        gemini_headers = self._inject_api_key(headers)

        if stream:
            return await self._forward_streaming(url, body, gemini_headers)
        return await self._forward_full(url, body, gemini_headers)

    async def _forward_full(
        self,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=body, headers=headers)
                return response.status_code, dict(response.headers), response.content
        except httpx.HTTPError as exc:
            raise GeminiError(f"Gemini request failed: {exc}") from exc

    async def _forward_streaming(
        self,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], AsyncIterator[bytes]]:
        """Return a tuple where the third element is an async byte iterator."""
        try:
            client = httpx.AsyncClient(timeout=self._timeout)
            request = client.build_request("POST", url, json=body, headers=headers)
            response = await client.send(request, stream=True)
        except httpx.HTTPError as exc:
            raise GeminiError(f"Gemini streaming request failed: {exc}") from exc

        async def _iter() -> AsyncIterator[bytes]:
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        return response.status_code, dict(response.headers), _iter()

    async def health_check(self) -> bool:
        """Return True if the Gemini API base URL is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(self._base_url)
                return r.status_code < 500
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def extract_usage(response_body: dict[str, Any]) -> dict[str, int]:
        """Extract token usage from a Gemini response body (best-effort)."""
        meta = response_body.get("usageMetadata", {})
        return {
            "prompt_token_count": meta.get("promptTokenCount", 0),
            "candidates_token_count": meta.get("candidatesTokenCount", 0),
            "total_token_count": meta.get("totalTokenCount", 0),
        }
