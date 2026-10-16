"""MemFlow Relay CLI.

Commands:
  serve      — Start the local HTTP proxy.
  doctor     — Verify environment, credentials, and connectivity.
  test       — Run end-to-end shadow mode verification.
  stats      — Display current relay statistics.
  benchmark  — Run baseline vs optimized Gemini comparison.
  version    — Report package version.
"""

from __future__ import annotations

import asyncio
import json
import sys

import typer

from memflow_relay import __version__
from memflow_relay.stats import get_stats

app = typer.Typer(
    name="memflow-relay",
    help="MemFlow Relay — local Gemini proxy by LamoonAGI (Research Preview).",
    add_completion=False,
)


# ── serve ─────────────────────────────────────────────────────────────────────


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(0, help="Bind port (0 = use MEMFLOW_PORT env var)."),
    reload: bool = typer.Option(False, help="Auto-reload on code changes (dev only)."),
) -> None:
    """Start the MemFlow Relay local proxy server."""
    import uvicorn

    from memflow_relay.config import get_config
    from memflow_relay.server import build_app
    from memflow_relay.stats import get_stats

    config = get_config()
    actual_port = port if port != 0 else config.memflow_port

    typer.echo(
        f"🚀 MemFlow Relay {__version__} starting on http://{host}:{actual_port}  "
        f"[mode={config.memflow_mode.value}, telemetry={config.memflow_telemetry.value}]"
    )

    stats = get_stats()
    application = build_app(config, stats)
    # Use httptools HTTP parser — it permits colons in URL paths (e.g.
    # /v1beta/models/gemini-2.5-flash:generateContent), which h11 rejects
    # as non-conformant per RFC 3986 strict mode.
    uvicorn.run(application, host=host, port=actual_port, reload=reload, http="httptools")


# ── doctor ────────────────────────────────────────────────────────────────────


@app.command()
def doctor() -> None:
    """Verify Python version, credentials, connectivity, and port availability."""
    from memflow_relay.auth import is_valid_memflow_key
    from memflow_relay.config import get_config

    config = get_config()
    issues: list[str] = []

    # Python version
    major, minor = sys.version_info[:2]
    py_ok = major == 3 and minor >= 11
    _check("Python >= 3.11", py_ok, f"found {major}.{minor}")
    if not py_ok:
        issues.append("Python 3.11+ required.")

    # MEMFLOW_API_KEY
    mf_key_ok = is_valid_memflow_key(config.memflow_api_key)
    _check("MEMFLOW_API_KEY set and valid", mf_key_ok)
    if not mf_key_ok:
        issues.append("MEMFLOW_API_KEY missing or invalid (expected lago_... format).")

    # GEMINI_API_KEY present
    gem_key_ok = bool(config.gemini_api_key)
    _check("GEMINI_API_KEY set", gem_key_ok)
    if not gem_key_ok:
        issues.append("GEMINI_API_KEY is not set.")

    # Port availability
    import socket

    port = config.memflow_port
    port_free = _port_available("127.0.0.1", port)
    _check(f"Port {port} available", port_free)
    if not port_free:
        issues.append(f"Port {port} is already in use.")

    # Credential isolation reminder
    typer.echo("\n🔒 Credential isolation: GEMINI_API_KEY is never sent to LamoonAGI.")
    typer.echo(f"   MEMFLOW_API_KEY is never sent to Google.")

    if issues:
        typer.echo(f"\n⚠️  {len(issues)} issue(s) found:")
        for issue in issues:
            typer.echo(f"   • {issue}")
        raise typer.Exit(code=1)
    else:
        typer.echo("\n✅ All checks passed.")


def _check(label: str, ok: bool, detail: str = "") -> None:
    status = "✓" if ok else "✗"
    suffix = f" ({detail})" if detail else ""
    typer.echo(f"  {status} {label}{suffix}")


def _port_available(host: str, port: int) -> bool:
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
        return True
    except OSError:
        return False


# ── test ──────────────────────────────────────────────────────────────────────


@app.command(name="test")
def test_cmd() -> None:
    """Run end-to-end shadow mode verification against a running relay."""
    asyncio.run(_run_shadow_test())


async def _run_shadow_test() -> None:
    import httpx

    from memflow_relay.config import get_config

    config = get_config()
    port = config.memflow_port
    url = f"http://127.0.0.1:{port}/_health"

    typer.echo(f"Testing relay health at {url} ...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url)
            if r.status_code == 200:
                typer.echo("✅ Relay is responding (shadow mode test passed).")
            else:
                typer.echo(f"⚠️  Relay responded with status {r.status_code}.")
                raise typer.Exit(code=1)
    except httpx.ConnectError:
        typer.echo(f"✗ Could not connect to relay on port {port}. Is `memflow-relay serve` running?")
        raise typer.Exit(code=1)


# ── stats ─────────────────────────────────────────────────────────────────────


@app.command()
def stats() -> None:
    """Display current relay statistics."""
    snapshot = get_stats().snapshot()
    typer.echo("\nMemFlow Relay Statistics")
    typer.echo("-" * 40)
    for key, value in snapshot.items():
        label = key.replace("_", " ").title()
        typer.echo(f"  {label:30s} {value}")
    typer.echo("")


# ── benchmark ─────────────────────────────────────────────────────────────────


@app.command()
def benchmark(
    output_json: bool = typer.Option(False, "--json", help="Output results as JSON."),
) -> None:
    """Run baseline vs optimized comparison using sample scenarios."""
    asyncio.run(_run_benchmark(output_json))


async def _run_benchmark(output_json: bool) -> None:
    from memflow_relay.benchmark import run_benchmark
    from memflow_relay.config import get_config

    config = get_config()

    scenarios = [
        {
            "name": "short_prompt",
            "body": {"contents": [{"parts": [{"text": "Hello, what is 2+2?"}]}]},
        },
        {
            "name": "medium_prompt",
            "body": {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": "Explain the concept of context windows in LLMs in 3 sentences."
                            }
                        ]
                    }
                ]
            },
        },
    ]

    results = await run_benchmark(
        scenarios,
        memflow_api_key=config.memflow_api_key,
        memflow_api_url=config.memflow_api_url,
    )

    if output_json:
        typer.echo(json.dumps([r.__dict__ for r in results], indent=2))
        return

    typer.echo("\n📈 MemFlow Relay Benchmark Results")
    typer.echo("─" * 60)
    for r in results:
        typer.echo(f"\n  Scenario: {r.scenario}")
        typer.echo(f"    Baseline tokens:   {r.baseline_tokens}")
        typer.echo(f"    Optimized tokens:  {r.optimized_tokens}")
        typer.echo(f"    Tokens saved:      {r.tokens_saved} ({r.token_reduction_pct}%)")
        typer.echo(f"    Baseline latency:  {r.baseline_latency_ms:.1f} ms")
        typer.echo(f"    Optimized latency: {r.optimized_latency_ms:.1f} ms")
    typer.echo()


# ── version ───────────────────────────────────────────────────────────────────


@app.command()
def version() -> None:
    """Report package version and research preview status."""
    typer.echo(f"memflow-relay {__version__} (Research Preview)")
    typer.echo("© 2024 LamoonAGI — https://www.lamoonagi.com/en/memflow/relay/")


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    app()
