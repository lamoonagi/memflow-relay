# Contributing to MemFlow Relay

Thank you for your interest in contributing! MemFlow Relay is developed by LamoonAGI and community contributions are welcome.

## Development Setup

```bash
git clone https://github.com/lamoonagi/memflow-relay.git
cd memflow-relay
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

## Code Style

- Python 3.11+ type annotations required on all public functions.
- Format with `ruff format`.
- Lint with `ruff check`.
- All new code must have accompanying tests.

## Security Rules

- **Never** log, print, or include `GEMINI_API_KEY`, `MEMFLOW_API_KEY`, Bearer tokens, or cookies in any output.
- All log/telemetry output must go through `security.redaction.redact()`.
- Shadow mode invariant must not be broken: the request forwarded to Gemini must equal the original client request.

## Pull Requests

1. Fork the repository.
2. Create a feature branch: `git checkout -b feat/your-feature`.
3. Commit your changes with a clear message.
4. Open a PR against `main`.

## Reporting Issues

For security issues see [SECURITY.md](SECURITY.md). For other bugs, open a GitHub issue.
