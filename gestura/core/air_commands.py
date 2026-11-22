# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""AIR COMMAND radial wheel: the allow-listed command set and its ordering.

The wheel never accepts a free-form command. Every sector maps to an id in this
tuple, and every id must also exist in ``core.gesture_registry.COMMANDS`` (a test
enforces this). Launching happens through ``controllers.air_actions`` which uses
fixed argument lists — no shell, no user-supplied string ever reaches the OS.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AirCommand:
    id: str
    label: str
    glyph: str
    category: str
    confirm: bool = False


#: Glyphs are plain ASCII so they render identically in every font and skin
#: (emoji glyphs come out in colour, which breaks the monochrome HUD look).
AIR_COMMANDS: tuple[AirCommand, ...] = (
    AirCommand("app.open_browser", "Open browser", "WEB", "Launch"),
    AirCommand("app.open_calculator", "Calculator", "123", "Launch"),
    AirCommand("app.open_file_manager", "File manager", "FILE", "Launch"),
    AirCommand("app.screenshot", "Screenshot", "CAP", "Capture"),
    AirCommand("app.toggle_keyboard", "Virtual keyboard", "KEY", "AirDesk"),
    AirCommand("mode.air_mouse", "AIR MOUSE", "MOVE", "Mode"),
    AirCommand("mode.air_keyboard", "AIR KEYBOARD", "TYPE", "Mode"),
    AirCommand("mode.presentation", "Presentation", "SHOW", "Mode"),
    AirCommand("media.volume_up", "Volume +", "VOL+", "Media"),
    AirCommand("media.volume_down", "Volume -", "VOL-", "Media"),
    AirCommand("media.play_pause", "Play / pause", "PLAY", "Media"),
    AirCommand("app.toggle_pause", "Pause tracking", "PAUSE", "Safety"),
)

AIR_COMMAND_IDS: tuple[str, ...] = tuple(command.id for command in AIR_COMMANDS)
AIR_COMMAND_BY_ID: dict[str, AirCommand] = {command.id: command for command in AIR_COMMANDS}


def get(command_id: str) -> AirCommand | None:
    return AIR_COMMAND_BY_ID.get(command_id)


def labels() -> list[tuple[str, str]]:
    """(id, label) pairs, for combo boxes."""
    return [(command.id, command.label) for command in AIR_COMMANDS]
