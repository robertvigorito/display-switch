"""Typer command line interface for Display Switch."""

from __future__ import annotations

import click
import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def cli() -> None:
    """Enable or disable Windows monitors individually or in named groups."""


@app.command()
def show() -> int:
    """Open the Display Switch window."""
    from .gui import run_gui  # Imported lazily so --help works without loading Qt.

    return run_gui()


def main() -> int:
    """Run the command line interface and return the process exit status.

    Returns:
        0 on success, otherwise the exit status of the failing command.
    """
    try:
        result = app(standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except click.exceptions.Exit as exc:
        return exc.exit_code
    return result if isinstance(result, int) else 0
