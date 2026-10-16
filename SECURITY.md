# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✓         |

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

To report a vulnerability, email **security@lamoonagi.com** with:

1. A description of the vulnerability and its potential impact.
2. Steps to reproduce or a proof-of-concept.
3. Any suggested mitigations.

We aim to acknowledge receipt within **48 hours** and provide an initial assessment within **5 business days**.

## Security Guarantees

- `GEMINI_API_KEY` is used **exclusively** to authenticate requests to `generativelanguage.googleapis.com`. It is never transmitted to `api.lamoonagi.com`, logged, or included in telemetry.
- `MEMFLOW_API_KEY` is used **exclusively** to authenticate requests to `api.lamoonagi.com`. It is never forwarded to Google.
- All logs, exception messages, and telemetry events pass through centralized secret redaction before being written or transmitted.
- Shadow mode enforces an immutable invariant: the request forwarded to Gemini is byte-identical to the original client request.
