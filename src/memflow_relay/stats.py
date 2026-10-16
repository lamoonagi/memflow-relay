"""Request statistics tracker for MemFlow Relay."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class RelayStats:
    """Thread-safe, mutable stats for the relay process lifetime."""

    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)

    requests_total: int = 0
    """Total relay requests received."""

    requests_analyzed: int = 0
    """Requests where the optimizer was consulted."""

    requests_optimized: int = 0
    """Requests where an optimization was applied."""

    requests_bypassed: int = 0
    """Requests forwarded unchanged (shadow mode, fail-open, or safe-fallback)."""

    estimated_tokens_saved: int = 0
    """Estimated number of input tokens saved across all optimized requests."""

    total_latency_ms: float = 0.0
    """Cumulative relay latency (milliseconds)."""

    start_time: float = field(default_factory=time.time)
    """Epoch timestamp when the relay started."""

    # ── Mutation helpers ─────────────────────────────────────────────────────

    def record_bypass(self) -> None:
        with self._lock:
            self.requests_total += 1
            self.requests_bypassed += 1

    def record_optimized(self, tokens_saved: int = 0, latency_ms: float = 0.0) -> None:
        with self._lock:
            self.requests_total += 1
            self.requests_analyzed += 1
            self.requests_optimized += 1
            self.estimated_tokens_saved += max(0, tokens_saved)
            self.total_latency_ms += latency_ms

    def record_analyzed_bypass(self, latency_ms: float = 0.0) -> None:
        """Optimizer was consulted but decided not to optimize (safe fallback)."""
        with self._lock:
            self.requests_total += 1
            self.requests_analyzed += 1
            self.requests_bypassed += 1
            self.total_latency_ms += latency_ms

    # ── Read-only helpers ────────────────────────────────────────────────────

    @property
    def optimization_rate(self) -> float:
        """Fraction of analyzed requests that were optimized (0.0–1.0)."""
        with self._lock:
            if self.requests_analyzed == 0:
                return 0.0
            return self.requests_optimized / self.requests_analyzed

    @property
    def average_latency_ms(self) -> float:
        with self._lock:
            if self.requests_total == 0:
                return 0.0
            return self.total_latency_ms / self.requests_total

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    def snapshot(self) -> dict:
        """Return a JSON-serializable point-in-time snapshot."""
        with self._lock:
            # Compute derived values inline — do NOT call properties that
            # also acquire self._lock (threading.Lock is non-reentrant).
            opt_rate = (
                self.requests_optimized / self.requests_analyzed
                if self.requests_analyzed > 0 else 0.0
            )
            avg_latency = (
                self.total_latency_ms / self.requests_total
                if self.requests_total > 0 else 0.0
            )
            return {
                "requests_total": self.requests_total,
                "requests_analyzed": self.requests_analyzed,
                "requests_optimized": self.requests_optimized,
                "requests_bypassed": self.requests_bypassed,
                "estimated_tokens_saved": self.estimated_tokens_saved,
                "optimization_rate": round(opt_rate, 4),
                "average_latency_ms": round(avg_latency, 1),
                "uptime_seconds": round(time.time() - self.start_time, 1),
            }


# Process-level singleton
_stats = RelayStats()


def get_stats() -> RelayStats:
    """Return the process-level stats singleton."""
    return _stats


def reset_stats() -> None:
    """Reset stats — used in tests only."""
    global _stats
    _stats = RelayStats()
