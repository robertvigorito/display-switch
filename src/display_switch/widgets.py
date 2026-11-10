"""Pill-shaped on/off switch widget."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractButton, QWidget

ON_COLOR = QColor("#2f7de1")
OFF_COLOR = QColor("#b8bec7")
KNOB_COLOR = QColor("#ffffff")
TRACK_WIDTH = 44
TRACK_HEIGHT = 24
KNOB_MARGIN = 3


class ToggleSwitch(QAbstractButton):
    """Checkable switch that paints itself as a sliding pill."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(TRACK_WIDTH, TRACK_HEIGHT)

    def sizeHint(self) -> QSize:
        """Return the fixed switch size.

        Returns:
            The size of the switch track.
        """
        return QSize(TRACK_WIDTH, TRACK_HEIGHT)

    def paintEvent(self, _event: QPaintEvent) -> None:
        """Draw the track and the knob for the current state.

        Args:
            _event: The paint event, unused.

        Returns:
            None
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1.0 if self.isEnabled() else 0.45)
        painter.setPen(Qt.PenStyle.NoPen)

        track = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(ON_COLOR if self.isChecked() else OFF_COLOR)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)

        knob = track.height() - 2 * KNOB_MARGIN
        left = track.left() + KNOB_MARGIN
        right = track.right() - KNOB_MARGIN - knob
        x = right if self.isChecked() else left
        painter.setBrush(KNOB_COLOR)
        painter.drawEllipse(QRectF(x, track.top() + KNOB_MARGIN, knob, knob))
        painter.end()
