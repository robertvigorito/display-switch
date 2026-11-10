"""PyInstaller entry point for Display Switch.

Runs the Typer CLI. With no arguments it opens the GUI, matching display-switch.bat.
"""

import sys

from display_switch.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("show")
    raise SystemExit(main())
