# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
"""Two-hand chord engine and its assignment validation."""

from __future__ import annotations

import pytest

from gestura.core.gesture_registry import COMMANDS
from gestura.gestures.chords import (
    DEFAULT_CHORDS,
    CHORD_NAMES,
    ChordEngine,
    parse_chord,
    validate_assignments,
)


def test_parse_chord_accepts_known_names():
    assert parse_chord("left_fist+right_two_fingers") == ("fist", "two_fingers")
    assert parse_chord("left_open_palm+right_fist") == ("open_palm", "fist")


@pytest.mark.parametrize("name", ["fist+point", "left_grip+right_point", "left_fist", ""])
def test_parse_chord_rejects_unknown_poses(name):
    with pytest.raises(ValueError):
        parse_chord(name)


def test_default_assignments_are_valid_chords_and_allow_listed_commands():
    assert set(DEFAULT_CHORDS) == set(CHORD_NAMES)
    for name, command in DEFAULT_CHORDS.items():
        parse_chord(name)
        assert command in COMMANDS


def test_validate_assignments_drops_unknown_chords_and_commands():
    cleaned = validate_assignments(
        {"left_fist+right_point": "mouse.left_click",
         "left_grip+right_point": "mouse.left_click",
         "left_fist+right_two_fingers": "evil.shell"},
        set(COMMANDS),
    )
    assert cleaned == {"left_fist+right_point": "mouse.left_click"}


def test_chord_fires_once_until_a_hand_changes_pose():
    engine = ChordEngine(min_frames=2)
    assert engine.update("fist", "two_fingers", now=10.0) is None
    match = engine.update("fist", "two_fingers", now=10.1)
    assert match is not None and match.command == "media.volume_up"
    assert engine.update("fist", "two_fingers", now=10.2) is None


def test_chord_requires_min_frames():
    engine = ChordEngine(min_frames=3)
    assert engine.update("fist", "two_fingers", now=0.0) is None
    assert engine.update("fist", "two_fingers", now=0.05) is None
    assert engine.update("fist", "two_fingers", now=0.1) is not None


def test_chord_cooldown_applies_after_pose_change():
    engine = ChordEngine(min_frames=1, cooldown_s=1.0)
    assert engine.update("point", "fist", now=0.0) is not None
    assert engine.update("open_palm", "point", now=0.2) is None  # unmapped pose
    assert engine.update("point", "fist", now=0.5) is None  # still cooling down
    assert engine.update("point", "fist", now=1.2) is not None


def test_missing_hand_resets_the_chord():
    engine = ChordEngine(min_frames=2)
    engine.update("fist", "two_fingers", now=0.0)
    assert engine.update(None, "two_fingers", now=0.1) is None
    assert engine.update("fist", "two_fingers", now=0.2) is None
    assert engine.update("fist", "two_fingers", now=0.3) is not None


def test_unmapped_pose_never_fires():
    engine = ChordEngine(min_frames=1)
    assert engine.update("fist", "fist", now=0.0) is None
