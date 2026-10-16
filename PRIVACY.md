# Privacy Notice — MemFlow Relay

**Last updated:** 2024

MemFlow Relay is a **local** proxy process that runs on your machine. This notice describes what data leaves your machine and under what circumstances.

---

## What data is collected

### Telemetry mode: `off`
No data leaves your machine. Nothing is transmitted to LamoonAGI.

### Telemetry mode: `metrics_only` (default)
Aggregate, non-personal metrics are transmitted to LamoonAGI:
- Request counts (analyzed, optimized, bypassed).
- Estimated token counts (input/output token size buckets, not content).
- Latency percentiles.
- Operating mode (`shadow`, `safe`, `optimize`).
- Package version.

**Raw prompt content is never included in `metrics_only` telemetry.**

### Telemetry mode: `diagnostic`
In addition to `metrics_only` data:
- Anonymized request structure metadata (e.g. number of messages, role distribution).
- Error codes and exception types (messages are redacted).

**Even in `diagnostic` mode, raw prompt text, API keys, and personally identifiable information are never transmitted.**

---

## What is never transmitted to LamoonAGI

- `GEMINI_API_KEY` or any Google credential.
- Raw prompt or completion content.
- User-identifiable information from request bodies.
- Bearer tokens or session cookies from incoming requests.

---

## Data retention

Aggregate metrics are retained for 90 days for service improvement purposes and then deleted.

---

## Contact

privacy@lamoonagi.com
