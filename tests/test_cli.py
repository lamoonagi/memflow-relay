"""Tests for the CLI commands using Typer's test runner."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from memflow_relay import __version__
from memflow_relay.cli import app

runner = CliRunner()


class TestVersionCommand:
    def test_version_output(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.output
        assert "Research Preview" in result.output
        assert "LamoonAGI" in result.output

    def test_version_no_error(self):
        result = runner.invoke(app, ["version"])
        assert result.exception is None


class TestStatsCommand:
    def test_stats_output(self):
        result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        assert "Requests Total" in result.output or "requests_total" in result.output.lower()

    def test_stats_shows_optimization_rate(self):
        result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        assert "Optimization Rate" in result.output or "optimization" in result.output.lower()


class TestDoctorCommand:
    def test_doctor_with_no_keys_exits_nonzero(self, monkeypatch):
        """Doctor should fail when keys are not configured."""
        monkeypatch.delenv("MEMFLOW_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        result = runner.invoke(app, ["doctor"])
        # Exit code 1 because keys are missing
        assert result.exit_code == 1

    def test_doctor_shows_credential_isolation_reminder(self, monkeypatch):
        monkeypatch.delenv("MEMFLOW_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        result = runner.invoke(app, ["doctor"])
        output = result.output
        assert "GEMINI_API_KEY" in output
        assert "LamoonAGI" in output or "MEMFLOW_API_KEY" in output

    def test_doctor_with_valid_keys_shows_checks(self, monkeypatch):
        monkeypatch.setenv("MEMFLOW_API_KEY", "lago_testkey1234567890abcde")
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyFakeGeminiKeyForTest")
        result = runner.invoke(app, ["doctor"])
        # Should show check marks
        assert "✓" in result.output or "✗" in result.output


class TestHelpCommand:
    def test_help_exits_zero(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_help_lists_commands(self):
        result = runner.invoke(app, ["--help"])
        assert "serve" in result.output
        assert "doctor" in result.output
        assert "stats" in result.output
        assert "benchmark" in result.output
        assert "version" in result.output
