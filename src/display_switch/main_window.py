"""PySide6 main window: a slim list of monitor and group switches."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import monitor_backend as mb
from .group_dialog import GroupDialog
from .groups import Group, GroupStore
from .widgets import ToggleSwitch

STYLE = """
QMainWindow, QScrollArea, QWidget#content, QWidget#qt_scrollarea_viewport { background: #f5f6f8; }
QScrollArea { border: none; }
QLabel#title { font-size: 18px; font-weight: 600; color: #1f2328; }
QLabel#section { font-size: 11px; font-weight: 600; color: #6b7280; }
QLabel#name { font-size: 14px; color: #1f2328; }
QLabel#detail { font-size: 12px; color: #8a8f98; }
QFrame#row { background: #ffffff; border: 1px solid #e3e6eb; border-radius: 10px; }
QPushButton { background: #ffffff; border: 1px solid #d0d4da; border-radius: 6px; padding: 5px 12px; color: #1f2328; }
QPushButton:hover { background: #eef2f7; }
QPushButton:disabled { color: #9ca3af; }
"""


def _label(text: str, object_name: str) -> QLabel:
    """Create a styled label.

    Args:
        text: Label text.
        object_name: Object name used by the stylesheet.

    Returns:
        The configured label.
    """
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setWordWrap(True)
    return label


def _make_switch(checked: bool, on_toggle: Callable[[bool], None]) -> ToggleSwitch:
    """Create a toggle switch that calls back when the user flips it.

    Args:
        checked: Initial state of the switch.
        on_toggle: Callback receiving the new state.

    Returns:
        The connected switch.
    """
    switch = ToggleSwitch()
    switch.setChecked(checked)
    switch.toggled.connect(on_toggle)
    return switch


def _make_row(title: str, detail: str, toggle: ToggleSwitch, extra: QWidget | None = None) -> QFrame:
    """Create a card with a name, a status line, optional button, and a toggle.

    Args:
        title: Main text, such as the monitor or group name.
        detail: Secondary text shown under the title.
        toggle: Switch placed at the right edge.
        extra: Optional widget placed before the switch.

    Returns:
        The card widget.
    """
    frame = QFrame()
    frame.setObjectName("row")
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(14, 10, 14, 10)
    texts = QVBoxLayout()
    texts.setSpacing(2)
    texts.addWidget(_label(title, "name"))
    texts.addWidget(_label(detail, "detail"))
    layout.addLayout(texts, 1)
    if extra is not None:
        layout.addWidget(extra)
    layout.addWidget(toggle)
    return frame


def _clear_layout(layout: QVBoxLayout) -> None:
    """Remove and schedule deletion of every widget in a layout.

    Args:
        layout: Layout to empty.

    Returns:
        None
    """
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget() if item is not None else None
        if widget is not None:
            widget.deleteLater()


class _TaskSignals(QObject):
    done = Signal(object, object)  # (callback, result)
    failed = Signal(str)


class _Task(QRunnable):
    """Runs a blocking backend call off the GUI thread."""

    def __init__(self, fn: Callable[..., Any], args: tuple, on_done: Callable[[Any], None], parent: QObject) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._on_done = on_done
        self.signals = _TaskSignals(parent)
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            result = self._fn(*self._args)
        except Exception as exc:  # surfaced to the user by the window
            self.signals.failed.emit(str(exc))
            return
        self.signals.done.emit(self._on_done, result)


class MainWindow(QMainWindow):
    """Main window listing monitor switches and group switches."""

    def __init__(self, store: GroupStore, admin: bool) -> None:
        super().__init__()
        self.setWindowTitle("Display Switch")
        self.resize(420, 620)
        self.setStyleSheet(STYLE)
        self._store = store
        self._monitors: list[mb.Monitor] = []
        self._pool = QThreadPool.globalInstance()
        self._build_ui()

        if not admin:
            self.statusBar().showMessage("Not running as administrator: enabling and disabling monitors will fail.")
        self._render()
        self.refresh_monitors()

    # ----- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        """Create the header, the scrollable card list, and the footer."""
        self._central = QWidget()
        self.setCentralWidget(self._central)
        root = QVBoxLayout(self._central)
        root.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.setContentsMargins(16, 12, 16, 4)
        header.addWidget(_label("Display Switch", "title"))
        header.addStretch(1)
        copy_log = QPushButton("Copy PS")
        copy_log.setToolTip("Copy the PowerShell commands run so far, for troubleshooting")
        copy_log.clicked.connect(lambda _=False: self._copy_powershell_log())
        header.addWidget(copy_log)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(lambda _=False: self.refresh_monitors())
        header.addWidget(refresh)
        root.addLayout(header)

        self._content = QWidget()
        self._content.setObjectName("content")
        self._list = QVBoxLayout(self._content)
        self._list.setContentsMargins(16, 8, 16, 8)
        self._list.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._content)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(16, 4, 16, 12)
        new_button = QPushButton("+ New group")
        new_button.clicked.connect(lambda _=False: self._new_group())
        footer.addStretch(1)
        footer.addWidget(new_button)
        root.addLayout(footer)

    def _render(self) -> None:
        """Rebuild the monitor and group cards from the current state."""
        _clear_layout(self._list)
        self._list.addWidget(_label("MONITORS", "section"))
        if not self._monitors:
            self._list.addWidget(_label("No monitors found. Press Refresh.", "detail"))
        for monitor in self._monitors:
            toggle = _make_switch(monitor.enabled, lambda checked, m=monitor: self._change([m.instance_id], checked))
            detail = "Enabled" if monitor.enabled else "Disabled"
            self._list.addWidget(_make_row(monitor.name, detail, toggle))

        self._list.addSpacing(8)
        self._list.addWidget(_label("GROUPS", "section"))
        if not self._store.groups:
            self._list.addWidget(_label("No groups yet. Press New group.", "detail"))
        for group in self._store.groups:
            self._list.addWidget(self._group_row(group))
        self._list.addStretch(1)

    def _group_row(self, group: Group) -> QFrame:
        """Create the card for one group.

        Args:
            group: Group to display.

        Returns:
            The card widget with an Edit button and a switch.
        """
        present = self._connected(group)
        on = bool(present) and all(m.enabled for m in present)
        if group.monitor_ids:
            detail = f"{len(present)} of {len(group.monitor_ids)} connected"
        else:
            detail = "No monitors"
        toggle = _make_switch(on, lambda checked, g=group: self._change_group(g, checked))
        toggle.setEnabled(bool(present))
        edit = QPushButton("Edit")
        edit.clicked.connect(lambda _=False, g=group: self._edit_group(g))
        return _make_row(group.name, detail, toggle, edit)

    # ----- background tasks ------------------------------------------------

    def _run(self, fn: Callable[..., Any], *args: Any, on_done: Callable[[Any], None], status: str) -> None:
        self.statusBar().showMessage(status)
        self._central.setEnabled(False)
        task = _Task(fn, args, on_done, parent=self)
        task.signals.done.connect(self._dispatch)
        task.signals.failed.connect(self._on_failed)
        self._pool.start(task)

    def _dispatch(self, callback: Callable[[Any], None], result: Any) -> None:
        self._central.setEnabled(True)
        callback(result)

    def _on_failed(self, message: str) -> None:
        self._central.setEnabled(True)
        self.statusBar().showMessage("Operation failed.")
        QMessageBox.warning(self, "Error", message)

    # ----- monitors --------------------------------------------------------

    def _copy_powershell_log(self) -> None:
        """Copy the logged PowerShell commands and their results to the clipboard."""
        records = mb.command_log()
        if not records:
            self.statusBar().showMessage("No PowerShell commands have run yet.")
            return
        QGuiApplication.clipboard().setText(mb.format_command_log(records))
        self.statusBar().showMessage(f"Copied {len(records)} PowerShell command(s) to the clipboard.")

    def refresh_monitors(self) -> None:
        """Scan monitors in the background and redraw the cards."""
        self._run(mb.list_monitors, on_done=self._on_monitors_loaded, status="Scanning monitors...")

    def _on_monitors_loaded(self, monitors: list[mb.Monitor]) -> None:
        self._monitors = monitors
        self._render()
        self.statusBar().showMessage(f"{len(monitors)} monitor(s) found.")

    def _change(self, instance_ids: list[str], enabled: bool) -> None:
        if not instance_ids:
            return
        status = "Enabling..." if enabled else "Disabling..."
        self._run(mb.apply_change, instance_ids, enabled, on_done=self._on_change_done, status=status)

    def _on_change_done(self, result: mb.ChangeResult) -> None:
        if result.failed:
            details = "\n".join(f"{iid}: {err}" for iid, err in result.failed.items())
            QMessageBox.warning(self, "Some changes failed", details)
        self.statusBar().showMessage(f"Done: {len(result.succeeded)} succeeded, {len(result.failed)} failed.")
        self.refresh_monitors()

    # ----- groups ----------------------------------------------------------

    def _connected(self, group: Group) -> list[mb.Monitor]:
        """Return the currently connected monitors that belong to a group.

        Args:
            group: Group to check.

        Returns:
            Connected monitors in the group.
        """
        return [m for m in self._monitors if m.instance_id in group.monitor_ids]

    def _change_group(self, group: Group, enabled: bool) -> None:
        targets = [m.instance_id for m in self._connected(group)]
        if not targets:
            self.statusBar().showMessage("No connected monitors in this group.")
            self._render()
            return
        self._change(targets, enabled)

    def _save(self) -> bool:
        try:
            self._store.save()
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", f"Could not save groups: {exc}")
            return False
        return True

    def _new_group(self) -> None:
        dialog = GroupDialog(
            self, title="New group", name="", monitors=self._monitors, members=[], allow_delete=False
        )
        dialog.exec()
        if not dialog.saved:
            return
        try:
            group = self._store.add(dialog.group_name())
        except ValueError as exc:
            QMessageBox.warning(self, "Group", str(exc))
            return
        self._store.set_members(group.name, dialog.member_ids())
        if self._save():
            self._render()

    def _edit_group(self, group: Group) -> None:
        dialog = GroupDialog(
            self,
            title="Edit group",
            name=group.name,
            monitors=self._monitors,
            members=group.monitor_ids,
            allow_delete=True,
        )
        dialog.exec()
        if dialog.delete_requested:
            self._delete_group(group)
            return
        if not dialog.saved:
            return
        new_name = dialog.group_name()
        try:
            self._store.rename(group.name, new_name)
        except ValueError as exc:
            QMessageBox.warning(self, "Group", str(exc))
            return
        self._store.set_members(new_name, dialog.member_ids())
        if self._save():
            self._render()

    def _delete_group(self, group: Group) -> None:
        answer = QMessageBox.question(self, "Delete group", f"Delete group '{group.name}'?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._store.delete(group.name)
        if self._save():
            self._render()
