"""Configuration for MemFlow Relay.

All settings are loaded from environment variables (or a .env file).
No defaults expose credentials; API keys must be set explicitly.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RelayMode(str, Enum):
    """Operating mode for the relay."""

    shadow = "shadow"
    """Observe only — forward original request to Gemini unchanged."""

    safe = "safe"
    """Optimize when confidence is high; fall back to original on any doubt."""

    optimize = "optimize"
    """Always attempt MemFlow optimization."""


class TelemetryMode(str, Enum):
    """Telemetry verbosity level."""

    off = "off"
    """No telemetry transmitted."""

    metrics_only = "metrics_only"
    """Aggregate counts and token-size buckets. NO raw prompt content."""

    diagnostic = "diagnostic"
    """Adds anonymized request-structure metadata. Still no raw prompts."""


class RelayConfig(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        # Do NOT set env_file here — pydantic-settings performs a filesystem
        # stat() at class-body evaluation time which blocks on NTFS/WSL mounts.
        # Users who want .env loading should pass env_file explicitly:
        #   RelayConfig(_env_file=".env")
        # or set MEMFLOW_* environment variables directly.
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Credentials ──────────────────────────────────────────────────────────

    memflow_api_key: Annotated[
        str | None,
        Field(default=None, description="LamoonAGI API key (lago_ prefix). Never sent to Google."),
    ] = None

    gemini_api_key: Annotated[
        str | None,
        Field(default=None, description="Google Gemini API key. Never sent to LamoonAGI."),
    ] = None

    # ── Endpoints ────────────────────────────────────────────────────────────

    memflow_api_url: str = Field(
        default="https://api.lamoonagi.com",
        description="MemFlow optimizer API base URL.",
    )

    # ── Behaviour ────────────────────────────────────────────────────────────

    memflow_mode: RelayMode = Field(
        default=RelayMode.shadow,
        description="Operating mode: shadow | safe | optimize.",
    )

    memflow_telemetry: TelemetryMode = Field(
        default=TelemetryMode.metrics_only,
        description="Telemetry level: off | metrics_only | diagnostic.",
    )

    memflow_port: Annotated[int, Field(ge=1, le=65535)] = Field(
        default=8765,
        description="Local proxy port (binds to 127.0.0.1 only).",
    )

    memflow_fail_open: bool = Field(
        default=True,
        description="Forward original request when optimizer is unavailable.",
    )

    # ── Gemini upstream ───────────────────────────────────────────────────────

    gemini_api_base_url: str = Field(
        default="https://generativelanguage.googleapis.com",
        description="Gemini API base URL.",
    )

    # ── Timeouts ─────────────────────────────────────────────────────────────

    optimizer_timeout_seconds: float = Field(
        default=3.0,
        description="Timeout for MemFlow optimizer calls (seconds).",
    )

    @field_validator("memflow_api_key", mode="before")
    @classmethod
    def _validate_memflow_key(cls, v: str | None) -> str | None:
        if v is not None and v.strip() == "":
            return None
        return v

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def _validate_gemini_key(cls, v: str | None) -> str | None:
        if v is not None and v.strip() == "":
            return None
        return v


@lru_cache(maxsize=1)
def get_config() -> RelayConfig:
    """Return a cached singleton config instance."""
    return RelayConfig()
