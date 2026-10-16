# Changelog

All notable changes to `memflow-relay` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.1.0] — 2024

### Added
- Initial research preview release.
- Local HTTP proxy server listening on `127.0.0.1:8765`.
- Shadow, safe, and optimize operating modes.
- Gemini API provider adapter with streaming support.
- Centralized secret redaction for all logs and telemetry.
- Telemetry modes: `off`, `metrics_only`, `diagnostic`.
- Fail-open default when MemFlow optimizer is unavailable.
- CLI commands: `serve`, `doctor`, `test`, `stats`, `benchmark`, `version`.
- Full pytest test suite covering shadow invariant, credential isolation, fail-open, and secret redaction.
