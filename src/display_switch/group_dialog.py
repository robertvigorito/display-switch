"""Dialog for creating, editing, and deleting a display group."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .monitor_backend import Monitor


class GroupDialog(QDialog):
    """Edit a group name and its member monitors."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        title: str,
        name: str,
        monitors: list[Monitor],
        members: list[str],
        allow_delete: bool,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(320)
        self.saved = False
        self.delete_requested = False
        self._original_members = list(members)
        self._connected_ids = {m.instance_id for m in monitors}

        layout = QVBoxLayout(self)
        self._name = QLineEdit(name)
        self._name.setPlaceholderText("Group name")
        layout.addWidget(self._name)

        self._checks: dict[str, QCheckBox] = {}
        for monitor in monitors:
            check = QCheckBox(monitor.name)
            check.setChecked(monitor.instance_id in members)
            check.setToolTip(monitor.instance_id)
            self._checks[monitor.instance_id] = check
            layout.addWidget(check)

        kept = [iid for iid in members if iid not in self._connected_ids]
        if kept:
            layout.addWidget(QLabel(f"{len(kept)} disconnected monitor(s) will be kept."))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        if allow_delete:
            delete = buttons.addButton("Delete", QDialogButtonBox.ButtonRole.DestructiveRole)
            delete.clicked.connect(lambda _=False: self._on_delete())
        layout.addWidget(buttons)

    def group_name(self) -> str:
        """Return the entered group name without surrounding whitespace.

        Returns:
            The trimmed group name.
        """
        return self._name.text().strip()

    def member_ids(self) -> list[str]:
        """Return the checked monitors plus disconnected members, which are kept.

        Returns:
            Monitor instance IDs for the group.
        """
        checked = [iid for iid, check in self._checks.items() if check.isChecked()]
        kept = [iid for iid in self._original_members if iid not in self._connected_ids]
        return kept + checked

    def _on_save(self) -> None:
        """Validate the name and accept the dialog."""
        if not self.group_name():
            QMessageBox.warning(self, "Group", "Group name cannot be empty.")
            return
        self.saved = True
        self.accept()

    def _on_delete(self) -> None:
        """Close the dialog and flag the group for deletion."""
        self.delete_requested = True
        self.reject()
