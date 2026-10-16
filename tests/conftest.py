"""Shared pytest fixtures for memflow-relay tests."""
from __future__ import annotations

import pytest

from memflow_relay.security.redaction import _clear_runtime_secrets
from memflow_relay.stats import reset_stats


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset process-level singletons before each test."""
    from memflow_relay import config as cfg_module

    cfg_module.get_config.cache_clear()
    reset_stats()
    _clear_runtime_secrets()

    yield

    cfg_module.get_config.cache_clear()
    reset_stats()
    _clear_runtime_secrets()
