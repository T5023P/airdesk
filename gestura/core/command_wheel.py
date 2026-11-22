# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Pure state machine for the AIR COMMAND radial wheel.

Nothing here touches Qt, OpenCV or the OS: the caller feeds three booleans plus
the right index-fingertip position, and receives immutable updates. That keeps
the interaction fully unit-testable and keeps the wheel unable to execute
anything by itself.

Interaction
-----------
* A left-hand gesture held for ``activation_hold_ms`` opens the wheel.
* The right index fingertip selects the sector it points to (outside the dead
  zone); the sector under the finger is reported as ``selected``.
* A pinch edge on the confirming hand reports ``confirmed`` with the selected id
  and closes the wheel (the pinch must re-open before it can fire again).
* The cancel gesture held for ``cancel_hold_ms`` closes without a command.
* Closing starts a cooldown, so the same gesture cannot immediately re-open it.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Sequence

from .air_commands import AIR_COMMAND_IDS

TWO_PI = 2.0 * math.pi


@dataclass(frozen=True, slots=True)
class WheelUpdate:
    """What changed on this frame."""

    active: bool
    selected: str | None = None
    confirmed: str | None = None
    just_opened: bool = False
    just_closed: bool = False
    cancelled: bool = False
    progress: float = 0.0  # 0..1 activation hold progress, for UI feedback


class CommandWheel:
    def __init__(
        self,
        commands: Sequence[str] = AIR_COMMAND_IDS,
        *,
        activation_hold_s: float = 0.25,
        cancel_hold_s: float = 0.32,
        dead_zone: float = 0.10,
        cooldown_s: float = 0.9,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not commands:
            raise ValueError("the wheel needs at least one command")
        self.commands = tuple(commands)
        self.activation_hold_s = float(activation_hold_s)
        self.cancel_hold_s = float(cancel_hold_s)
        self.dead_zone = float(dead_zone)
        self.cooldown_s = float(cooldown_s)
        self._clock = clock
        self.active = False
        self.selected: str | None = None
        self._opened_at = 0.0
        self._activation_since: float | None = None
        self._cancel_since: float | None = None
        self._not_before = 0.0
        self._confirm_armed = True
        self._confirm_was_closed = False

    # ------------------------------------------------------------------ maths
    def sector_of(self, x: float, y: float) -> int | None:
        """Sector index under a normalised point, or None inside the dead zone.

        Sector 0 starts at 12 o'clock and numbering proceeds clockwise.
        """
        dx, dy = float(x) - 0.5, float(y) - 0.5
        if math.hypot(dx, dy) < self.dead_zone:
            return None
        angle = math.atan2(dx, -dy)  # 0 at the top, increasing clockwise
        if angle < 0:
            angle += TWO_PI
        return int(angle / TWO_PI * len(self.commands)) % len(self.commands)

    def command_at(self, x: float, y: float) -> str | None:
        sector = self.sector_of(x, y)
        return None if sector is None else self.commands[sector]

    # ----------------------------------------------------------------- update
    def update(
        self,
        *,
        activation: bool,
        cancel: bool = False,
        confirm_closed: bool = False,
        pointer: tuple[float, float] | None = None,
        now: float | None = None,
    ) -> WheelUpdate:
        now = self._clock() if now is None else float(now)
        just_opened = False
        just_closed = False
        cancelled = False
        confirmed: str | None = None
        progress = 0.0

        if not self.active:
            self._activation_since = self._hold_start(self._activation_since, activation, now)
            if self._activation_since is not None and now >= self._not_before:
                progress = min(1.0, (now - self._activation_since) / max(1e-3, self.activation_hold_s))
                if now - self._activation_since >= self.activation_hold_s:
                    self.active = True
                    self._opened_at = now
                    self._activation_since = None
                    self._cancel_since = None
                    self.selected = None
                    just_opened = True
                    progress = 0.0
            return WheelUpdate(
                active=self.active,
                selected=self.selected,
                just_opened=just_opened,
                progress=progress,
            )

        # ---- active: selection, confirmation, cancellation
        if pointer is not None:
            self.selected = self.command_at(*pointer)

        closed = bool(confirm_closed)
        if closed and not self._confirm_was_closed and self._confirm_armed and self.selected:
            confirmed = self.selected
            self._confirm_armed = False
            self.active = False
            self.selected = None
            self._not_before = now + self.cooldown_s
            just_closed = True
        if not closed:
            self._confirm_armed = True
        self._confirm_was_closed = closed

        if self.active and now - self._opened_at >= 0.35:
            self._cancel_since = self._hold_start(self._cancel_since, cancel, now)
            if self._cancel_since is not None and now - self._cancel_since >= self.cancel_hold_s:
                cancelled = True
                self.active = False
                self.selected = None
                self._cancel_since = None
                self._not_before = now + self.cooldown_s
                just_closed = True
        elif not cancel:
            self._cancel_since = None

        return WheelUpdate(
            active=self.active,
            selected=self.selected,
            confirmed=confirmed,
            just_opened=False,
            just_closed=just_closed,
            cancelled=cancelled,
        )

    # ------------------------------------------------------------------ misc
    def close(self) -> None:
        """Close without a command (tracking lost, emergency stop, mode change)."""
        self.active = False
        self.selected = None
        self._cancel_since = None
        self._activation_since = None
        self._not_before = 0.0

    @staticmethod
    def _hold_start(since: float | None, condition: bool, now: float) -> float | None:
        if not condition:
            return None
        return now if since is None else since
