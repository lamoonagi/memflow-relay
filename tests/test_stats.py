"""Unit tests for stats.py."""
from __future__ import annotations

import pytest

from memflow_relay.stats import RelayStats, get_stats, reset_stats


class TestRelayStats:
    def test_initial_state(self):
        s = RelayStats()
        assert s.requests_total == 0
        assert s.requests_analyzed == 0
        assert s.requests_optimized == 0
        assert s.requests_bypassed == 0
        assert s.estimated_tokens_saved == 0

    def test_record_bypass_increments(self):
        s = RelayStats()
        s.record_bypass()
        assert s.requests_total == 1
        assert s.requests_bypassed == 1
        assert s.requests_optimized == 0

    def test_record_optimized_increments(self):
        s = RelayStats()
        s.record_optimized(tokens_saved=100, latency_ms=5.0)
        assert s.requests_total == 1
        assert s.requests_optimized == 1
        assert s.requests_analyzed == 1
        assert s.estimated_tokens_saved == 100

    def test_record_analyzed_bypass(self):
        s = RelayStats()
        s.record_analyzed_bypass(latency_ms=3.0)
        assert s.requests_total == 1
        assert s.requests_analyzed == 1
        assert s.requests_bypassed == 1
        assert s.requests_optimized == 0

    def test_optimization_rate_zero_when_no_analyzed(self):
        s = RelayStats()
        assert s.optimization_rate == 0.0

    def test_optimization_rate_full(self):
        s = RelayStats()
        s.record_optimized(tokens_saved=50)
        assert s.optimization_rate == 1.0

    def test_optimization_rate_half(self):
        s = RelayStats()
        s.record_optimized(tokens_saved=50)
        s.record_analyzed_bypass()
        assert s.optimization_rate == 0.5

    def test_average_latency(self):
        s = RelayStats()
        s.record_optimized(latency_ms=10.0)
        s.record_optimized(latency_ms=20.0)
        assert s.average_latency_ms == 15.0

    def test_negative_tokens_saved_clamped_to_zero(self):
        s = RelayStats()
        s.record_optimized(tokens_saved=-50)
        assert s.estimated_tokens_saved == 0

    def test_snapshot_returns_dict(self):
        s = RelayStats()
        s.record_bypass()
        snap = s.snapshot()
        assert isinstance(snap, dict)
        assert snap["requests_total"] == 1
        assert "optimization_rate" in snap
        assert "uptime_seconds" in snap

    def test_reset_stats(self):
        get_stats().record_bypass()
        reset_stats()
        assert get_stats().requests_total == 0

    def test_singleton_returns_same_object(self):
        s1 = get_stats()
        s2 = get_stats()
        assert s1 is s2
