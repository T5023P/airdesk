# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Sequential macro execution with delays, cancellation and a hard time budget.

The runner knows nothing about the OS: it calls a ``dispatch`` callable supplied
by the controllers layer, which is where the allow-lists live. Sleeping and the
clock are injectable so the ordering/delay behaviour is unit-tested without
real waits.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .model import Macro, MacroAction

MAX_RUN_SECONDS = 30.0


@dataclass(slots=True)
class RunResult:
    macro_id: str
    ok: bool
    needs_confirmation: bool = False
    lines: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return " · ".join(self.lines) if self.lines else "No steps run"


class MacroRunner:
    def __init__(
        self,
        dispatch: Callable[[MacroAction], str],
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._dispatch = dispatch
        self._sleep = sleep
        self._clock = clock

    def run(self, macro: Macro, *, confirmed: bool = False) -> RunResult:
        if not macro.enabled:
            return RunResult(macro.id, ok=False, lines=["Macro is disabled"])
        if macro.confirm and not confirmed:
            return RunResult(macro.id, ok=False, needs_confirmation=True,
                             lines=[f"Confirm “{macro.name}”"])

        started = self._clock()
        lines: list[str] = []
        for action in macro.actions:
            if action.delay_ms:
                self._sleep(action.delay_ms / 1000.0)
            if self._clock() - started > MAX_RUN_SECONDS:
                lines.append("Stopped: macro took too long")
                return RunResult(macro.id, ok=False, lines=lines)
            try:
                lines.append(self._dispatch(action))
            except Exception as exc:  # noqa: BLE001 - one bad step must not kill tracking
                lines.append(f"Step failed: {exc}")
                return RunResult(macro.id, ok=False, lines=lines)
        return RunResult(macro.id, ok=True, lines=lines)
