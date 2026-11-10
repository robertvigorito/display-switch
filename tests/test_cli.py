"""Tests for the Typer command line interface."""

from __future__ import annotations

import sys
import types

import pytest
from typer.testing import CliRunner

from display_switch import cli


def test_help_lists_show_command(runner: CliRunner) -> None:
    """Help output lists the show command.

    Args:
        runner: Typer test runner.

    Returns:
        None
    """
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "show" in result.output


def test_show_starts_gui(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """The show command runs the GUI entry point.

    Args:
        runner: Typer test runner.
        monkeypatch: Pytest fixture used to replace the GUI module.

    Returns:
        None
    """
    calls: list[str] = []
    fake_gui = types.ModuleType("display_switch.gui")

    def fake_run_gui() -> int:
        calls.append("run")
        return 0

    fake_gui.run_gui = fake_run_gui  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "display_switch.gui", fake_gui)

    result = runner.invoke(cli.app, ["show"])

    assert result.exit_code == 0
    assert calls == ["run"]


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer test runner.

    Returns:
        A new CliRunner instance.
    """
    return CliRunner()
