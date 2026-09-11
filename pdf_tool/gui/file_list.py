"""The file list widget and its two-line row renderer."""

from __future__ import annotations


from PySide6.QtCore import QMargins, QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from ..units import human_size

ROLE_PATH = Qt.ItemDataRole.UserRole        # absolute path (str)
ROLE_PAGES = Qt.ItemDataRole.UserRole + 1   # int pages, or None while probing
ROLE_SIZE = Qt.ItemDataRole.UserRole + 2    # int bytes, or None

ROW_HEIGHT = 46


class FileItemDelegate(QStyledItemDelegate):
    """Draws each row as a bold file name over a muted details line."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._muted = QColor("#9aa1b0")
        self._accent = QColor("#6c8cff")

    def sizeHint(self, option, index):  # noqa: N802 (Qt naming)
        hint = super().sizeHint(option, index)
        hint.setHeight(max(hint.height(), ROW_HEIGHT))
        return hint

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()
        try:
            rect: QRect = option.rect
            selected = bool(option.state & QStyle.StateFlag.State_Selected)

            if selected:
                painter.setBrush(QColor(37, 41, 50))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 8, 8)

            margins = QMargins(12, 4, 12, 4)
            inner = rect.marginsRemoved(margins)

            title_font = QFont(option.font)
            title_font.setWeight(QFont.Weight.DemiBold)

            details_font = QFont(option.font)
            base_pt = option.font.pointSizeF()
            if base_pt > 0:
                details_font.setPointSizeF(base_pt * 0.9)
            elif option.font.pixelSize() > 0:  # pixel-sized fonts report -1 points
                details_font.setPixelSize(max(1, int(option.font.pixelSize() * 0.9)))

            name = index.data(Qt.ItemDataRole.DisplayRole) or ""
            pages = index.data(ROLE_PAGES)
            size = index.data(ROLE_SIZE)

            name_color = self._accent if selected else option.palette.color(
                option.palette.ColorRole.Text
            )

            # title line
            painter.setFont(title_font)
            painter.setPen(name_color)
            title_rect = QRect(inner.left(), inner.top(), inner.width(), inner.height() // 2)
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft |
                             Qt.AlignmentFlag.AlignVCenter, name)

            # details line
            painter.setFont(details_font)
            if pages is None:
                details = "counting pages…"
            else:
                parts = [f"{pages} page{'s' if pages != 1 else ''}"]
                if size is not None:
                    parts.append(human_size(size))
                details = " · ".join(parts)
            detail_rect = QRect(inner.left(), inner.top() + inner.height() // 2,
                                inner.width(), inner.height() // 2)
            painter.setPen(self._muted)
            painter.drawText(detail_rect, Qt.AlignmentFlag.AlignLeft |
                             Qt.AlignmentFlag.AlignVCenter, details)
        finally:
            painter.restore()
