# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""AIR MACROS: validated, allow-listed multi-step gesture actions."""

from __future__ import annotations

from .model import (
    ALLOWED_APPS,
    ALLOWED_SHORTCUTS,
    ALLOWED_TRIGGERS,
    Macro,
    MacroAction,
    MacroBook,
    new_macro,
    new_action,
)
from .runner import MacroRunner, RunResult
from .store import MacroStore, default_macro_path

__all__ = [
    "ALLOWED_APPS",
    "ALLOWED_SHORTCUTS",
    "ALLOWED_TRIGGERS",
    "Macro",
    "MacroAction",
    "MacroBook",
    "MacroRunner",
    "MacroStore",
    "RunResult",
    "default_macro_path",
    "new_action",
    "new_macro",
]
