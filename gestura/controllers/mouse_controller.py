# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Mouse actions on top of an InputBackend."""

from __future__ import annotations

import logging
from typing import Callable

from ..config.settings import CursorSettings
from ..services.display_service import Display, map_normalized, select_display
from .backends import InputBackend

log = logging.getLogger(__name__)


class MouseController:
    # Keep our own cursor 1 px away from the exact screen corners so it can
    # never trip PyAutoGUI's fail-safe; only a *physical* mouse moved into a
    # corner does that, which is the intended emergency gesture.
    EDGE_INSET = 1

    def __init__(
        self,
        backend: InputBackend,
        settings: CursorSettings,
        displays: Callable[[], list[Display]] | None = None,
    ) -> None:
        self.backend = backend
        self.settings = settings
        self._last: tuple[int, int] | None = None
        self._scroll_rem = [0.0, 0.0]
        self._size: tuple[int, int] | None = None
        self._dragging = False
        # Multi-monitor support: AIRDESK maps onto the *selected* display. With
        # no provider (tests, headless), behaviour is exactly the old single
        # primary-monitor mapping.
        self._display_provider = displays
        self._displays: list[Display] = []
        self._display_index = 0
        self._settling = False
        self._settle_px = 140

    # ------------------------------------------------------------- displays
    def refresh_displays(self, selected: int | None = None) -> list[Display]:
        self._displays = list(self._display_provider()) if self._display_provider else []
        if selected is not None:
            self._display_index = max(0, int(selected))
        self._display_index = min(self._display_index, max(0, len(self._displays) - 1))
        self.invalidate_screen()
        return self._displays

    @property
    def displays(self) -> list[Display]:
        if self._display_provider is not None and not self._displays:
            self.refresh_displays(self._display_index)
        return self._displays

    @property
    def active_display(self) -> Display | None:
        return select_display(self.displays, self._display_index)

    def select_display_index(self, index: int, *, settle_px: int | None = None) -> None:
        """Switch display. The next cursor move is rate-limited so it cannot
        teleport across the desktop; the pointer glides to the new mapping."""
        if index == self._display_index:
            return
        self._display_index = max(0, int(index))
        if settle_px is not None:
            self._settle_px = max(20, int(settle_px))
        self._settling = True
        self._last = None

    def _physical_scale(self) -> float:
        """Ratio between backend pixel space and Qt logical geometry.

        Qt reports device-independent pixels; PyAutoGUI/SetCursorPos and XTest
        use physical pixels. The ratio is derived from the primary display so a
        125 %/150 % Windows scale factor still lands the cursor where aimed.
        """
        primary = next((d for d in self.displays if d.primary), None)
        if primary is None or primary.width <= 0:
            return 1.0
        try:
            width, _ = self.screen_size()
        except Exception:  # noqa: BLE001 - backend without a display
            return 1.0
        return width / primary.width if width > 0 else 1.0

    def screen_size(self) -> tuple[int, int]:
        if self._size is None:
            self._size = self.backend.screen_size()
        return self._size

    def invalidate_screen(self) -> None:
        self._size = None
        self._last = None

    def to_pixels(self, u: float, v: float) -> tuple[int, int]:
        display = self.active_display
        if display is not None and display.valid:
            x, y = map_normalized(u, v, display)
            scale = self._physical_scale()
            if scale != 1.0:
                x = int(round(x * scale))
                y = int(round(y * scale))
            return x, y
        w, h = self.screen_size()
        i = self.EDGE_INSET
        x = int(round(u * (w - 1)))
        y = int(round(v * (h - 1)))
        return min(w - 1 - i, max(i, x)), min(h - 1 - i, max(i, y))

    def move_normalized(self, u: float, v: float) -> bool:
        """Move the cursor; returns False when inside the dead zone."""
        x, y = self.to_pixels(u, v)
        if self._settling and self._last is not None:
            # After a display switch, approach the new mapping in bounded steps.
            dx, dy = x - self._last[0], y - self._last[1]
            limit = self._settle_px
            if abs(dx) > limit or abs(dy) > limit:
                x = self._last[0] + max(-limit, min(limit, dx))
                y = self._last[1] + max(-limit, min(limit, dy))
        if self._last is not None:
            dz = self.settings.dead_zone_px
            if abs(x - self._last[0]) <= dz and abs(y - self._last[1]) <= dz:
                return False
        self.backend.move_to(x, y)
        self._last = (x, y)
        if self._settling and (abs(x - self.to_pixels(u, v)[0]) <= 2
                               and abs(y - self.to_pixels(u, v)[1]) <= 2):
            self._settling = False
        return True

    def left_click(self) -> None:
        self.backend.click("left", 1)

    def right_click(self) -> None:
        self.backend.click("right", 1)

    def middle_click(self) -> None:
        self.backend.click("middle", 1)

    def double_click(self) -> None:
        self.backend.click("left", 2)

    @property
    def dragging(self) -> bool:
        return self._dragging

    def drag_start(self) -> None:
        if not self._dragging:
            self.backend.mouse_down("left")
            self._dragging = True

    def drag_end(self) -> None:
        if self._dragging:
            self._dragging = False
            self.backend.mouse_up("left")

    def release_buttons(self) -> None:
        """Called on stop / pause / emergency: never leave the button held."""
        self.drag_end()

    def scroll(self, dx: float, dy: float) -> None:
        """dx/dy in wheel notches (may be fractional)."""
        if self.backend.fractional_scroll:
            if dy:
                self.backend.scroll(dy)
            if dx:
                self.backend.hscroll(dx)
            return
        # Integer-only backends: accumulate the fractional part between frames.
        for axis, val in ((1, dy), (0, dx)):
            if not val:
                continue
            self._scroll_rem[axis] += val
            whole = int(self._scroll_rem[axis])
            if whole:
                self._scroll_rem[axis] -= whole
                (self.backend.scroll if axis == 1 else self.backend.hscroll)(whole)

    def reset(self) -> None:
        self.release_buttons()
        self._last = None
        self._scroll_rem = [0.0, 0.0]
