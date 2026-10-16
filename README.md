# MemFlow Relay

> **Research Preview** — MemFlow Relay is currently in research preview. APIs and behaviours may change without prior notice.

**MemFlow Relay** is a local HTTP proxy for Gemini API requests, developed by [LamoonAGI](https://www.lamoonagi.com). It transparently intercepts your Gemini calls and — depending on the configured operating mode — can analyse, optimise, or shadow-test context window usage before forwarding the request to Google Gemini.

---

## Features

- **Shadow mode** — observe without modification; original request is always forwarded unchanged.
- **Safe mode** — apply optimizations only when confidence is high; fall back to original on any doubt.
- **Optimize mode** — apply MemFlow context optimizations and track token savings.
- **Fail-open default** — if the MemFlow optimizer is unreachable or times out, the relay always forwards the original request to Gemini.
- **Credential isolation** — `GEMINI_API_KEY` never leaves your machine; it is never sent to LamoonAGI or MemFlow cloud services.
- **Secret redaction** — all logs, exceptions, and telemetry automatically strip API keys, Bearer tokens, and cookies.
- **Telemetry modes** — `off`, `metrics_only` (default, no prompt content), or `diagnostic`.

---

## Installation

```bash
pip install memflow-relay
```

Requires Python ≥ 3.11.

---

## Quick Start

```bash
# Set credentials
export MEMFLOW_API_KEY="lago_your_key_here"
export GEMINI_API_KEY="your_gemini_key_here"

# Start relay in shadow mode (safe default)
memflow-relay serve

# Verify setup
memflow-relay doctor

# Show live stats
memflow-relay stats
```

Your Gemini SDK base URL should be set to `http://127.0.0.1:8765`.

---

## CLI Commands

| Command | Description |
|---|---|
| `memflow-relay serve` | Start the local proxy (default port 8765) |
| `memflow-relay doctor` | Verify credentials, connectivity, and port availability |
| `memflow-relay test` | Run end-to-end shadow mode verification |
| `memflow-relay stats` | Display analyzed / optimized / bypassed counts and token savings |
| `memflow-relay benchmark` | Run baseline vs optimized Gemini workload comparison |
| `memflow-relay version` | Report package version and research preview status |

---

## Configuration

All configuration is via environment variables. See `.env.example` for a full reference.

| Variable | Default | Description |
|---|---|---|
| `MEMFLOW_API_KEY` | — | LamoonAGI API key (required for optimize/safe modes) |
| `GEMINI_API_KEY` | — | Google Gemini API key (never sent to LamoonAGI) |
| `MEMFLOW_API_URL` | `https://api.lamoonagi.com` | MemFlow optimizer endpoint |
| `MEMFLOW_MODE` | `shadow` | Operating mode: `shadow`, `safe`, `optimize` |
| `MEMFLOW_TELEMETRY` | `metrics_only` | Telemetry level: `off`, `metrics_only`, `diagnostic` |
| `MEMFLOW_PORT` | `8765` | Local proxy port |
| `MEMFLOW_FAIL_OPEN` | `true` | Forward original request if optimizer fails |

---

## Security

See [SECURITY.md](SECURITY.md) for vulnerability disclosure policy.

**Key guarantee:** `GEMINI_API_KEY` is used exclusively to authenticate requests to `generativelanguage.googleapis.com`. It is never included in requests to `api.lamoonagi.com` or any other endpoint.

---

## License

MIT — see [LICENSE](LICENSE).

© 2024 LamoonAGI. MemFlow is a product of LamoonAGI. Powered by LamoonAGI Context VMM technology.
