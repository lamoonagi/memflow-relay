"""Benchmark module for MemFlow Relay.

Runs baseline (direct Gemini) vs optimized (MemFlow) workloads and
reports estimated token savings and latency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    scenario: str
    baseline_tokens: int
    optimized_tokens: int
    baseline_latency_ms: float
    optimized_latency_ms: float

    @property
    def tokens_saved(self) -> int:
        return max(0, self.baseline_tokens - self.optimized_tokens)

    @property
    def token_reduction_pct(self) -> float:
        if self.baseline_tokens == 0:
            return 0.0
        return round(self.tokens_saved / self.baseline_tokens * 100, 1)


async def run_benchmark(
    scenarios: list[dict[str, Any]],
    *,
    gemini_api_key: str | None = None,
    memflow_api_key: str | None = None,
    memflow_api_url: str = "https://api.lamoonagi.com",
    gemini_base_url: str = "https://generativelanguage.googleapis.com",
) -> list[BenchmarkResult]:
    """Run benchmark scenarios and return results.

    Each scenario dict should have:
      - ``name``: str label
      - ``body``: dict Gemini request body

    This is a stub that measures optimizer decision latency without
    making real Gemini calls (to avoid incurring API costs in CI).
    Replace with live calls for production benchmarking.
    """
    from memflow_relay.optimizer import MemFlowOptimizer

    optimizer = MemFlowOptimizer(
        api_key=memflow_api_key,
        api_url=memflow_api_url,
        fail_open=True,
    )

    results: list[BenchmarkResult] = []

    for scenario in scenarios:
        name = scenario.get("name", "unnamed")
        body: dict[str, Any] = scenario.get("body", {})

        # Baseline: measure a no-op round (simulating direct Gemini)
        t0 = time.monotonic()
        baseline_tokens = _estimate_tokens(body)
        baseline_latency = (time.monotonic() - t0) * 1000

        # Optimized: call optimizer, measure decision latency
        t1 = time.monotonic()
        opt = await optimizer.analyze(body, mode="optimize")
        opt_latency = (time.monotonic() - t1) * 1000

        optimized_tokens = baseline_tokens - opt.tokens_saved if opt.should_optimize else baseline_tokens

        results.append(
            BenchmarkResult(
                scenario=name,
                baseline_tokens=baseline_tokens,
                optimized_tokens=optimized_tokens,
                baseline_latency_ms=round(baseline_latency, 2),
                optimized_latency_ms=round(opt_latency, 2),
            )
        )

    return results


def _estimate_tokens(body: dict[str, Any]) -> int:
    """Rough token estimate from a request body (4 chars ≈ 1 token)."""
    import json
    raw = json.dumps(body)
    return max(1, len(raw) // 4)
