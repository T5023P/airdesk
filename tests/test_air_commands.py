# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
"""AIR COMMAND allow-list integrity."""

from __future__ import annotations

from gestura.core import air_commands
from gestura.core.air_commands import AIR_COMMANDS, AIR_COMMAND_IDS
from gestura.core import gesture_registry


def test_every_wheel_command_is_in_the_global_allow_list():
    for command in AIR_COMMANDS:
        assert command.id in gesture_registry.COMMANDS, command.id
        assert gesture_registry.COMMANDS[command.id].category in ("AIR COMMAND", "Media", "Gestura")


def test_ids_are_unique_and_labels_present():
    assert len(AIR_COMMAND_IDS) == len(set(AIR_COMMAND_IDS))
    for command in AIR_COMMANDS:
        assert command.label.strip()
        assert command.glyph.strip()


def test_wheel_covers_the_required_airdesk_commands():
    required = {
        "app.open_browser",
        "app.open_calculator",
        "app.open_file_manager",
        "app.screenshot",
        "app.toggle_keyboard",
        "mode.air_mouse",
        "mode.air_keyboard",
        "mode.presentation",
        "media.volume_up",
        "media.volume_down",
        "media.play_pause",
        "app.toggle_pause",
    }
    assert required == set(AIR_COMMAND_IDS)


def test_lookup_helpers():
    assert air_commands.get("app.open_browser").label == "Open browser"
    assert air_commands.get("does.not.exist") is None
    assert len(air_commands.labels()) == len(AIR_COMMANDS)


def test_launching_commands_are_simulated_in_test_mode():
    """Launching/capturing must not bypass test mode (only `control` commands do)."""
    for command_id in ("app.open_browser", "app.open_calculator", "app.open_file_manager",
                       "app.screenshot"):
        spec = gesture_registry.COMMANDS[command_id]
        assert spec.control is False
