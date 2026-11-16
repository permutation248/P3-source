"""CLI command: start the API server."""

from __future__ import annotations

import click


@click.command()
@click.option("--host", default="127.0.0.1", help="Bind host.")
@click.option("--port", default=8000, type=int, help="Bind port.")
@click.option("--reload", "do_reload", is_flag=True, default=False, help="Enable auto-reload.")
@click.option("--db-url", default=None, type=str, help="Database URL override.")
def serve(host: str, port: int, do_reload: bool, db_url: str | None) -> None:
    """Start the Anonymous-Prover API server."""
    import os

    import uvicorn

    # Pass db_url via environment so the app factory can pick it up
    if db_url:
        os.environ["ANONYMOUS_PROVER_DB_URL"] = db_url

    reload_dirs = ["src/"] if do_reload else None

    click.echo(f"Starting Anonymous-Prover API server on {host}:{port}")
    uvicorn.run(
        "anonymous_prover.api.app:create_app",
        host=host,
        port=port,
        reload=do_reload,
        reload_dirs=reload_dirs,
        factory=True,
    )
