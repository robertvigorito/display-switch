"""Qt window startup and administrator elevation."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from . import monitor_backend as mb
from .groups import GroupStore
from .main_window import MainWindow

ADMIN_CHECK_SCRIPT = (
    "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent())"
    ".IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)"
)


def _is_admin_via_powershell() -> bool:
    """Ask Windows whether the session that runs PowerShell is elevated.

    Returns:
        True when the Windows session is elevated, otherwise False.
    """
    try:
        output = mb.run_powershell(ADMIN_CHECK_SCRIPT)
    except mb.PowerShellError:
        return False
    return output.strip().lower() == "true"


def is_admin() -> bool:
    """Return whether the Windows session has administrator rights.

    Under WSL the check runs through powershell.exe, because the Linux
    process itself cannot see the Windows elevation state.

    Returns:
        True when elevated or when no Windows PowerShell is reachable, otherwise False.
    """
    if sys.platform == "win32":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except OSError:
            return False
    if not Path(mb.POWERSHELL_EXE).exists():
        return True
    return _is_admin_via_powershell()


def relaunch_as_admin() -> bool:
    """Restart the `show` command elevated through the UAC prompt.

    Returns:
        True when the elevated process was started, otherwise False.
    """
    frozen = getattr(sys, "frozen", False)
    params = "show" if frozen else "-m display_switch show"
    cwd = str(Path(__file__).resolve().parents[1])
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, cwd, 1)
    return result > 32


def run_gui() -> int:
    """Start the Display Switch window, elevating first on Windows when needed.

    Returns:
        The Qt event loop exit status, or 0 when the elevated copy takes over.
    """
    if sys.platform == "win32" and not is_admin() and relaunch_as_admin():
        return 0
    # Continue without elevation when the relaunch fails; the window shows a warning.

    app = QApplication(sys.argv)
    store = GroupStore(GroupStore.default_path())
    store.load()
    window = MainWindow(store, admin=is_admin())
    window.show()
    return app.exec()
