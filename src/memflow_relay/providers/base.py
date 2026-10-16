"""Provider base class and protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class BaseProvider(ABC):
    """Abstract base for upstream LLM providers."""

    @abstractmethod
    async def forward(
        self,
        path: str,
        body: dict[str, Any],
        headers: dict[str, str],
        *,
        stream: bool = False,
    ) -> tuple[int, dict[str, str], bytes | AsyncIterator[bytes]]:
        """Forward *body* to the provider endpoint.

        Returns ``(status_code, response_headers, body_or_stream)``.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider endpoint is reachable."""
