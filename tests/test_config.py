"""Unit tests for config.py."""
from __future__ import annotations

import pytest


def _make_config(**env):
    from memflow_relay.config import RelayConfig
    return RelayConfig(**env)


class TestRelayConfig:
    def test_defaults(self):
        cfg = _make_config()
        assert cfg.memflow_mode.value == "shadow"
        assert cfg.memflow_telemetry.value == "metrics_only"
        assert cfg.memflow_port == 8765
        assert cfg.memflow_fail_open is True
        assert cfg.memflow_api_key is None
        assert cfg.gemini_api_key is None

    def test_set_mode_optimize(self):
        cfg = _make_config(memflow_mode="optimize")
        assert cfg.memflow_mode.value == "optimize"

    def test_set_mode_safe(self):
        cfg = _make_config(memflow_mode="safe")
        assert cfg.memflow_mode.value == "safe"

    def test_invalid_mode_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            _make_config(memflow_mode="invalid")

    def test_set_telemetry_off(self):
        cfg = _make_config(memflow_telemetry="off")
        assert cfg.memflow_telemetry.value == "off"

    def test_invalid_telemetry_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            _make_config(memflow_telemetry="verbose")

    def test_empty_api_key_becomes_none(self):
        cfg = _make_config(memflow_api_key="  ")
        assert cfg.memflow_api_key is None

    def test_empty_gemini_key_becomes_none(self):
        cfg = _make_config(gemini_api_key="  ")
        assert cfg.gemini_api_key is None

    def test_port_range_invalid(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            _make_config(memflow_port=0)

    def test_port_range_valid(self):
        cfg = _make_config(memflow_port=9000)
        assert cfg.memflow_port == 9000

    def test_fail_open_false(self):
        cfg = _make_config(memflow_fail_open=False)
        assert cfg.memflow_fail_open is False

    def test_custom_api_url(self):
        cfg = _make_config(memflow_api_url="https://staging.lamoonagi.com")
        assert cfg.memflow_api_url == "https://staging.lamoonagi.com"
