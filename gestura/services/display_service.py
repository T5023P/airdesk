# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Display (monitor) discovery and normalized -> absolute cursor mapping.

Gestura originally mapped the hand onto the primary monitor only. AIRDESK maps it
onto a *selected* display's geometry instead. Qt reports screen geometry in the
same virtual-desktop coordinate space that Windows' ``SetCursorPos`` and X11's
``XTestFakeMotionEvent`` use (primary at 0,0, monitors to the left negative), so
the same math works on both platforms.

``enumerate_displays`` must run on the GUI thread; everything else is pure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

EDGE_INSET = 1


@dataclass(frozen=True, slots=True)
class Display:
    index: int
    name: str
    x: int
    y: int
    width: int
    height: int
    primary: bool = False

    @property
    def label(self) -> str:
        tag = " (primary)" if self.primary else ""
        return f"{self.name} · {self.width}×{self.height}{tag}"

    @property
    def valid(self) -> bool:
        return self.width > 0 and self.height > 0


def enumerate_displays() -> list[Display]:
    """Detected displays, primary first. Empty list when no GUI is available."""
    try:
        from PySide6.QtGui import QGuiApplication

        screens = QGuiApplication.screens()
    except Exception as exc:  # noqa: BLE001 - headless CI / no Qt platform
        log.debug("display enumeration unavailable: %s", exc)
        return []

    primary = QGuiApplication.primaryScreen()
    displays: list[Display] = []
    for index, screen in enumerate(screens):
        geo = screen.geometry()
        displays.append(
            Display(
                index=index,
                name=screen.name() or f"Display {index + 1}",
                x=geo.x(),
                y=geo.y(),
                width=geo.width(),
                height=geo.height(),
                primary=screen is primary,
            )
        )
    displays.sort(key=lambda d: (not d.primary, d.x, d.y))
    # Re-index so the settings value always refers to a stable, ordered list.
    return [
        Display(index=i, name=d.name, x=d.x, y=d.y, width=d.width, height=d.height, primary=d.primary)
        for i, d in enumerate(displays)
    ]


def select_display(displays: list[Display], index: int) -> Display | None:
    """Pick a display by index, falling back to primary, then to the first one."""
    if not displays:
        return None
    if 0 <= index < len(displays):
        return displays[index]
    for display in displays:
        if display.primary:
            return display
    return displays[0]


def map_normalized(
    u: float, v: float, display: Display, *, inset: int = EDGE_INSET
) -> tuple[int, int]:
    """Map 0..1 hand coordinates onto a display's absolute pixel rectangle.

    The cursor is kept ``inset`` pixels away from the edges so AIRDESK's own
    cursor can never trip PyAutoGUI's corner fail-safe (only a *physical* mouse
    moved into a corner should do that).
    """
    if not display.valid:
        raise ValueError("display has no usable geometry")
    u = min(1.0, max(0.0, float(u)))
    v = min(1.0, max(0.0, float(v)))
    pad = max(0, int(inset))
    span_x = max(0, display.width - 1 - 2 * pad)
    span_y = max(0, display.height - 1 - 2 * pad)
    x = display.x + pad + int(round(u * span_x))
    y = display.y + pad + int(round(v * span_y))
    return x, y


def clamp_to_display(x: int, y: int, display: Display) -> tuple[int, int]:
    """Keep an absolute point inside a display (used after arrangement changes)."""
    left = display.x
    top = display.y
    right = display.x + max(0, display.width - 1)
    bottom = display.y + max(0, display.height - 1)
    return min(right, max(left, int(x))), min(bottom, max(top, int(y)))
