# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Always-on-top radial menu drawn for AIR COMMAND.

The window never takes focus and never accepts mouse input: the wheel is driven
entirely by hand gestures, so pointing at a sector must not click whatever is
underneath it.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .. import theme
from ...core.air_commands import AIR_COMMANDS, AIR_COMMAND_BY_ID
from ...core.command_wheel import WheelUpdate

SIZE = 620
MARGIN = 10


class CommandWheelOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(SIZE, SIZE)
        self._selected: str | None = None
        self._progress = 0.0
        self._commands = AIR_COMMANDS

    # ------------------------------------------------------------------ state
    def set_state(self, update: WheelUpdate) -> None:
        self._selected = update.selected
        self._progress = update.progress
        if update.active:
            if not self.isVisible():
                self._center()
                self.show()
                self.raise_()
            self.update()
        elif update.just_closed or not update.active:
            self.hide()
            self._selected = None
            self.update()

    def clear(self) -> None:
        self.hide()
        self._selected = None
        self.update()

    @property
    def selected_command(self) -> str | None:
        return self._selected

    def _center(self) -> None:
        screen = QGuiApplication.screenAt(self.cursor().pos()) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.move(geo.center().x() - SIZE // 2, geo.center().y() - SIZE // 2)

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        area = QRectF(self.rect()).adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)
        radius = min(area.width(), area.height()) / 2
        center = area.center()

        # Glass backing disc
        p.setPen(QPen(QColor(53, 224, 208, 60), 1.5))
        p.setBrush(QColor(7, 12, 24, 216))
        p.drawEllipse(center, radius, radius)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(53, 224, 208, 34), 1))
        p.drawEllipse(center, radius - 14, radius - 14)

        count = len(self._commands)
        step = 360.0 / count
        inner = radius * 0.44
        outer = radius * 0.95

        for index, command in enumerate(self._commands):
            start = 90.0 - (index + 1) * step
            selected = command.id == self._selected
            if selected:
                p.setBrush(QColor(53, 224, 208, 66))
                p.setPen(QPen(QColor(theme.ACCENT), 2))
            else:
                p.setBrush(QColor(255, 255, 255, 8 if index % 2 else 4))
                p.setPen(QPen(QColor(120, 168, 214, 40), 1))
            wedge = QRectF(center.x() - outer, center.y() - outer, outer * 2, outer * 2)
            p.drawPie(wedge, int(start * 16), int(step * 16))

            mid = math.radians((index + 0.5) * step)
            gx = center.x() + math.sin(mid) * radius * 0.80
            gy = center.y() - math.cos(mid) * radius * 0.80
            lx = center.x() + math.sin(mid) * radius * 0.62
            ly = center.y() - math.cos(mid) * radius * 0.62

            glyph_font = QFont(self.font())
            glyph_font.setPointSizeF(9.5 if len(command.glyph) > 3 else 11.5)
            glyph_font.setBold(True)
            glyph_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
            p.setFont(glyph_font)
            p.setPen(QColor(theme.ACCENT if selected else "#bfe6ff"))
            p.drawText(QRectF(gx - 70, gy - 16, 140, 22),
                       Qt.AlignmentFlag.AlignCenter, command.glyph)

            label_font = QFont(self.font())
            label_font.setPointSizeF(7.6)
            label_font.setBold(selected)
            p.setFont(label_font)
            p.setPen(QColor("#ffffff" if selected else "#94b3d0"))
            p.drawText(QRectF(lx - 78, ly - 12, 156, 30),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                       command.label)

        # Hub
        p.setPen(QPen(QColor(53, 224, 208, 120), 1.5))
        p.setBrush(QColor(12, 22, 38, 245))
        p.drawEllipse(center, inner, inner)

        title_font = QFont(self.font())
        title_font.setPointSizeF(7.4)
        title_font.setBold(True)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.2)
        p.setFont(title_font)
        p.setPen(QColor(theme.ACCENT))
        p.drawText(QRectF(center.x() - inner, center.y() - inner * 0.62, inner * 2, 18),
                   Qt.AlignmentFlag.AlignCenter, "AIR COMMAND")

        selected = AIR_COMMAND_BY_ID.get(self._selected or "")
        value_font = QFont(self.font())
        value_font.setPointSizeF(10.5)
        value_font.setBold(True)
        p.setFont(value_font)
        p.setPen(QColor("#ffffff" if selected else "#6f89a6"))
        p.drawText(
            QRectF(center.x() - inner * 0.86, center.y() - 18, inner * 1.72, 44),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
            selected.label if selected else "Point to choose",
        )

        hint_font = QFont(self.font())
        hint_font.setPointSizeF(7.0)
        p.setFont(hint_font)
        p.setPen(QColor("#6f89a6"))
        p.drawText(
            QRectF(center.x() - inner, center.y() + inner * 0.34, inner * 2, 30),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
            "pinch to confirm · open palm to cancel",
        )

        # Activation progress ring
        if self._progress > 0:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(theme.ACCENT), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            rect = QRectF(center.x() - radius + 6, center.y() - radius + 6,
                          radius * 2 - 12, radius * 2 - 12)
            p.drawArc(rect, 90 * 16, int(-360 * 16 * min(1.0, self._progress)))
        p.end()
