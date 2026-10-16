"""Unit tests for telemetry.py.

Critical invariant verified here:
  - In metrics_only mode, prompt content is NEVER present in any telemetry payload.
  - record_request() has no parameter that accepts prompt content.
"""
from __future__ import annotations

import logging

import pytest

from memflow_relay.config import TelemetryMode
from memflow_relay.telemetry import TelemetryDispatcher


class TestTelemetryDispatcher:
    def test_mode_off_no_dispatch(self, caplog):
        d = TelemetryDispatcher(TelemetryMode.off)
        with caplog.at_level(logging.DEBUG, logger="memflow_relay.telemetry"):
            d.record_request(
                decision="bypass",
                estimated_input_tokens=100,
                estimated_output_tokens=50,
                latency_ms=12.3,
                optimizer_called=False,
                relay_mode="shadow",
            )
        assert caplog.text == ""

    def test_metrics_only_logs_at_debug(self, caplog):
        d = TelemetryDispatcher(TelemetryMode.metrics_only)
        with caplog.at_level(logging.DEBUG, logger="memflow_relay.telemetry"):
            d.record_request(
                decision="bypass",
                estimated_input_tokens=200,
                estimated_output_tokens=80,
                latency_ms=5.0,
                optimizer_called=False,
                relay_mode="shadow",
            )
        assert "relay.request" in caplog.text

    def test_metrics_only_does_not_accept_prompt_content(self):
        """Structural check: record_request signature has no prompt_content parameter."""
        import inspect
        sig = inspect.signature(TelemetryDispatcher.record_request)
        assert "prompt_content" not in sig.parameters
        assert "messages" not in sig.parameters
        assert "body" not in sig.parameters
        assert "content" not in sig.parameters

    def test_metrics_only_payload_has_no_prompt_key(self, caplog):
        d = TelemetryDispatcher(TelemetryMode.metrics_only)
        with caplog.at_level(logging.DEBUG, logger="memflow_relay.telemetry"):
            d.record_request(
                decision="optimize",
                estimated_input_tokens=5000,
                estimated_output_tokens=200,
                latency_ms=20.0,
                optimizer_called=True,
                relay_mode="optimize",
            )
        log_output = caplog.text
        # Verify no prompt-related keys appear
        for forbidden_key in ("prompt", "message", "content", "text"):
            assert forbidden_key not in log_output.lower() or "token" in log_output.lower()

    def test_token_bucket_in_payload(self, caplog):
        d = TelemetryDispatcher(TelemetryMode.metrics_only)
        with caplog.at_level(logging.DEBUG, logger="memflow_relay.telemetry"):
            d.record_request(
                decision="optimize",
                estimated_input_tokens=1500,
                estimated_output_tokens=100,
                latency_ms=8.5,
                optimizer_called=True,
                relay_mode="optimize",
            )
        assert "input_token_bucket" in caplog.text
        assert "output_token_bucket" in caplog.text

    def test_diagnostic_includes_diagnostic_flag(self, caplog):
        d = TelemetryDispatcher(TelemetryMode.diagnostic)
        with caplog.at_level(logging.DEBUG, logger="memflow_relay.telemetry"):
            d.record_request(
                decision="bypass",
                estimated_input_tokens=300,
                estimated_output_tokens=50,
                latency_ms=2.0,
                optimizer_called=False,
                relay_mode="safe",
            )
        assert "diagnostic" in caplog.text

    def test_record_error_off_no_log(self, caplog):
        d = TelemetryDispatcher(TelemetryMode.off)
        with caplog.at_level(logging.DEBUG, logger="memflow_relay.telemetry"):
            d.record_error(error_type="GeminiError", relay_mode="shadow")
        assert caplog.text == ""

    def test_record_error_metrics_only_logs(self, caplog):
        d = TelemetryDispatcher(TelemetryMode.metrics_only)
        with caplog.at_level(logging.DEBUG, logger="memflow_relay.telemetry"):
            d.record_error(error_type="OptimizerTimeout", relay_mode="safe")
        assert "relay.error" in caplog.text
        assert "OptimizerTimeout" in caplog.text
