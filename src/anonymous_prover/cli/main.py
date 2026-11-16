"""CLI entry point for Anonymous-Prover."""

from __future__ import annotations

import click

from .. import __version__


@click.group()
@click.version_option(__version__)
def cli() -> None:
    """Anonymous-Prover: AI-assisted Lean 4 verification platform."""
    pass


# Import and register subcommands
from .collect import collect  # noqa: E402
from .compare import compare  # noqa: E402
from .run import run  # noqa: E402
from .serve import serve  # noqa: E402

cli.add_command(run)
cli.add_command(collect)
cli.add_command(compare)
cli.add_command(serve)
