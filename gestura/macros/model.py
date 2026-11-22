# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Validated macro model.

A macro is a short, ordered list of *predefined* actions bound to a gesture.
There is no free-text command field: every ``target`` is checked against a fixed
allow-list here, so a macro file edited by hand still cannot run a shell command.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..config.settings import HandGesture, HeadGesture
from ..core.air_commands import AIR_COMMAND_IDS
from ..gestures.chords import CHORD_NAMES

ActionType = Literal[
    "open_app",
    "shortcut",
    "set_mode",
    "keyboard",
    "volume",
    "presentation",
    "air_command",
    "wait",
]

#: Applications AIRDESK may launch. Resolved to fixed argv by the controller.
ALLOWED_APPS: dict[str, str] = {
    "browser": "Web browser",
    "calculator": "Calculator",
    "file_manager": "File manager",
}

#: Keyboard shortcuts AIRDESK may press (parsed into controller hotkeys).
ALLOWED_SHORTCUTS: dict[str, str] = {
    "ctrl+c": "Copy",
    "ctrl+v": "Paste",
    "ctrl+x": "Cut",
    "ctrl+z": "Undo",
    "ctrl+s": "Save",
    "ctrl+a": "Select all",
    "ctrl+f": "Find",
    "alt+tab": "Switch window",
    "ctrl+tab": "Next tab",
    "ctrl+shift+tab": "Previous tab",
    "page_up": "Page up",
    "page_down": "Page down",
    "enter": "Enter",
    "esc": "Escape",
    "f5": "Refresh",
}

ALLOWED_MODES: dict[str, str] = {
    "mouse": "AIR MOUSE",
    "keyboard": "AIR KEYBOARD",
    "navigation": "Head navigation",
    "presentation": "Presentation",
}

ALLOWED_VOLUME: dict[str, str] = {"up": "Volume up", "down": "Volume down", "mute": "Mute"}

ALLOWED_DIRECTIONS: dict[str, str] = {"next": "Next slide", "prev": "Previous slide"}

#: Gestures a macro can be bound to. Wheel-only poses (left hand) are reached
#: through chords so they never fight the command wheel.
ALLOWED_TRIGGERS: tuple[str, ...] = tuple(
    [g.value for g in HandGesture]
    + [g.value for g in HeadGesture]
    + [f"chord.{name}" for name in CHORD_NAMES]
)


class MacroAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ActionType
    target: str = ""
    delay_ms: int = Field(120, ge=0, le=10000, title="Delay before this step (ms)")

    @model_validator(mode="after")
    def _validate_target(self) -> "MacroAction":
        allowed: dict[str, str] | None = {
            "open_app": ALLOWED_APPS,
            "shortcut": ALLOWED_SHORTCUTS,
            "set_mode": ALLOWED_MODES,
            "volume": ALLOWED_VOLUME,
            "presentation": ALLOWED_DIRECTIONS,
        }.get(self.type)
        if allowed is not None:
            if self.target not in allowed:
                raise ValueError(
                    f"{self.type}: target must be one of {', '.join(sorted(allowed))}"
                )
        elif self.type == "air_command":
            if self.target not in AIR_COMMAND_IDS:
                raise ValueError("air_command: unknown AIR COMMAND id")
        elif self.type not in ("keyboard", "wait"):
            raise ValueError(f"unsupported action type {self.type!r}")
        if self.type == "wait" and self.delay_ms == 0:
            raise ValueError("wait needs a non-zero delay")
        return self

    def describe(self) -> str:
        if self.type == "open_app":
            return f"Open {ALLOWED_APPS.get(self.target, self.target)}"
        if self.type == "shortcut":
            return f"Press {ALLOWED_SHORTCUTS.get(self.target, self.target)}"
        if self.type == "set_mode":
            return f"Switch to {ALLOWED_MODES.get(self.target, self.target)}"
        if self.type == "volume":
            return ALLOWED_VOLUME.get(self.target, self.target)
        if self.type == "presentation":
            return ALLOWED_DIRECTIONS.get(self.target, self.target)
        if self.type == "air_command":
            return f"AIR COMMAND · {self.target}"
        if self.type == "keyboard":
            return "Show the virtual keyboard"
        return f"Wait {self.delay_ms} ms"


class Macro(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = Field("New macro", min_length=1, max_length=60)
    gesture: str = "hand.pinch"
    enabled: bool = True
    confirm: bool = Field(False, title="Ask for confirmation before running")
    actions: list[MacroAction] = Field(default_factory=list, max_length=20)

    @field_validator("gesture")
    @classmethod
    def _known_gesture(cls, value: str) -> str:
        if value not in ALLOWED_TRIGGERS:
            raise ValueError("unknown trigger gesture")
        return value

    @model_validator(mode="after")
    def _needs_actions(self) -> "Macro":
        if not self.actions:
            raise ValueError("a macro needs at least one action")
        return self


class MacroBook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    macros: list[Macro] = Field(default_factory=list)


def new_action(action_type: ActionType, target: str = "", delay_ms: int = 150) -> MacroAction:
    return MacroAction(type=action_type, target=target, delay_ms=delay_ms)


def new_macro(name: str = "New macro", gesture: str = "hand.pinch") -> Macro:
    return Macro(
        name=name,
        gesture=gesture,
        actions=[new_action("air_command", "app.open_calculator", 0)],
    )
