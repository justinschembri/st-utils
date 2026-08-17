"""Standalone CLI for running rime-ingest outside Docker.

Sets path and FROST env vars before importing the ingest runtime so
``paths.py`` resolves correctly at import time.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import dotenv
import typer
from rich.console import Console

app = typer.Typer(
    help="Run rime-ingest with host paths (no Docker required).",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def _root() -> None:
    """Run rime-ingest with host paths (no Docker required)."""
    return None


def _apply_env_file(env_file: Path) -> None:
    if not env_file.is_file():
        console.print(f"[red]Env file not found:[/red] {env_file}")
        raise typer.Exit(1)
    dotenv.load_dotenv(env_file, override=True)
    console.print(f"Loaded env file: {env_file.resolve()}")


def _set_env(key: str, value: str | Path) -> None:
    os.environ[key] = str(value)


def _preflight(
    *,
    applications: Path,
    sensors: Path,
    credentials: Path,
    tokens: Path,
) -> None:
    errors: list[str] = []

    if not applications.is_file():
        errors.append(f"Application config file not found: {applications}")

    if not sensors.is_dir():
        errors.append(f"Sensor config directory not found: {sensors}")
    else:
        found = [
            f
            for f in sensors.rglob("*.*ml")
            if "template" not in f.stem
        ]
        if not found:
            errors.append(
                f"No sensor YAML configs found under: {sensors} "
                "(templates are skipped)"
            )

    if not credentials.is_dir():
        errors.append(f"Credentials directory not found: {credentials}")
    else:
        for name in ("frost_credentials.json", "application_credentials.json"):
            if not (credentials / name).is_file():
                console.print(
                    f"[yellow]Warning:[/yellow] missing {credentials / name}"
                )

    if not tokens.exists():
        tokens.mkdir(parents=True, exist_ok=True)
        console.print(f"Created tokens directory: {tokens}")
    elif not tokens.is_dir():
        errors.append(f"Tokens path exists but is not a directory: {tokens}")

    if not os.getenv("FROST_ENDPOINT"):
        console.print(
            "[yellow]Warning:[/yellow] FROST_ENDPOINT unset; "
            "will use the package default (localhost)."
        )

    if errors:
        for err in errors:
            console.print(f"[red]{err}[/red]")
        raise typer.Exit(1)


@app.command("run")
def run(
    env_file: Optional[Path] = typer.Option(
        None,
        "--env-file",
        help="Dotenv file to load before flags (CLI flags override).",
        exists=False,
        dir_okay=False,
        file_okay=True,
        resolve_path=True,
    ),
    applications: Optional[Path] = typer.Option(
        None,
        "--applications",
        help="Path to application-configs.yml (APPLICATION_CONFIG_FILE).",
        resolve_path=True,
    ),
    sensors: Optional[Path] = typer.Option(
        None,
        "--sensors",
        help="Directory of sensor YAML configs (SENSOR_CONFIG_PATH).",
        resolve_path=True,
    ),
    credentials: Optional[Path] = typer.Option(
        None,
        "--credentials",
        help="Credentials directory (RIME_CREDENTIALS_DIR).",
        resolve_path=True,
    ),
    tokens: Optional[Path] = typer.Option(
        None,
        "--tokens",
        help="OAuth tokens directory (RIME_TOKENS_DIR).",
        resolve_path=True,
    ),
    logs: Optional[Path] = typer.Option(
        None,
        "--logs",
        help="Log output directory (RIME_LOGS_DIR).",
        resolve_path=True,
    ),
    runtime: Optional[Path] = typer.Option(
        None,
        "--runtime",
        help="Runtime root directory (RIME_RUNTIME_DIR).",
        resolve_path=True,
    ),
    frost_endpoint: Optional[str] = typer.Option(
        None,
        "--frost-endpoint",
        help="FROST server URL(s), comma-separated (FROST_ENDPOINT).",
    ),
    frost_version: Optional[str] = typer.Option(
        None,
        "--frost-version",
        help="FROST STA version, e.g. v1.1 (FROST_VERSION).",
    ),
) -> None:
    """Start ingest in-process using host paths (Windows/Docker-free deploy)."""
    # Do not force container secret paths (/run/secrets/...).
    os.environ.pop("CONTAINER_ENVIRONMENT", None)

    if env_file is not None:
        _apply_env_file(env_file)

    if applications is not None:
        _set_env("APPLICATION_CONFIG_FILE", applications)
    if sensors is not None:
        _set_env("SENSOR_CONFIG_PATH", sensors)
    if credentials is not None:
        _set_env("RIME_CREDENTIALS_DIR", credentials)
    if tokens is not None:
        _set_env("RIME_TOKENS_DIR", tokens)
    if logs is not None:
        _set_env("RIME_LOGS_DIR", logs)
    if runtime is not None:
        _set_env("RIME_RUNTIME_DIR", runtime)
    if frost_endpoint is not None:
        _set_env("FROST_ENDPOINT", frost_endpoint)
    if frost_version is not None:
        _set_env("FROST_VERSION", frost_version)

    # Import after env is set so paths.py / config.py resolve correctly.
    from rime_ingest.paths import (
        APPLICATION_CONFIG_FILE,
        CREDENTIALS_DIR,
        SENSOR_CONFIG_PATH,
        TOKENS_DIR,
    )

    _preflight(
        applications=APPLICATION_CONFIG_FILE,
        sensors=SENSOR_CONFIG_PATH,
        credentials=CREDENTIALS_DIR,
        tokens=TOKENS_DIR,
    )

    console.print("[bold]Starting rime-ingest...[/bold]")
    console.print(f"  applications: {APPLICATION_CONFIG_FILE}")
    console.print(f"  sensors:      {SENSOR_CONFIG_PATH}")
    console.print(f"  credentials:  {CREDENTIALS_DIR}")
    console.print(f"  tokens:       {TOKENS_DIR}")
    console.print(
        f"  frost:        {os.getenv('FROST_ENDPOINT', '(package default)')}"
    )

    from rime_ingest.main import push_available

    push_available()


def main() -> None:
    """Console script entry point."""
    app()


if __name__ == "__main__":
    main()
