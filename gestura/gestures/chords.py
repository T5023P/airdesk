# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Two-hand gesture chords: left-hand modifier + right-hand pose.

Gestura's two-hand mouse already splits the hands into roles (one moves, one
clicks). AIRDESK adds a configurable *chord* on top of that split, so the left
hand can act as a modifier for modes and macros without disturbing cursor work:

    left hand  = modifier (fist, point, two fingers, three fingers, open palm)
    right hand = the pose it must hold at the same time

A chord fires once, after ``min_frames`` consecutive frames, and cannot repeat
until one of the hands changes pose. Recognition is pure Python: no Qt, no
MediaPipe imports.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Mapping

from ..config.settings import DEFAULT_CHORD_ASSIGNMENTS

#: Chord names use the form ``left_pose+right_pose``.
CHORD_NAMES: tuple[str, ...] = (
    "left_fist+right_point",
    "left_fist+right_two_fingers",
    "left_point+right_fist",
    "left_two_fingers+right_point",
    "left_three_fingers+right_point",
    "left_open_palm+right_fist",
)

#: Default assignments live in the settings model (single source of truth).
#: They avoid the wheel's activation (left fist) and cancel (left open palm)
#: while the wheel is open: the wheel consumes those poses and the chord engine
#: is only fed when the wheel is closed.
DEFAULT_CHORDS: dict[str, str] = dict(DEFAULT_CHORD_ASSIGNMENTS)

_LEFT_POSES = {"fist", "point", "two_fingers", "three_fingers", "open_palm"}
_RIGHT_POSES = {"fist", "point", "two_fingers", "three_fingers", "open_palm"}


@dataclass(frozen=True, slots=True)
class ChordMatch:
    name: str
    command: str


def parse_chord(name: str) -> tuple[str, str]:
    """Split ``left_x+right_y`` into pose names, validating both halves."""
    left, _, right = name.partition("+")
    if not left.startswith("left_") or not right.startswith("right_"):
        raise ValueError(f"invalid chord {name!r}")
    left_pose = left.removeprefix("left_")
    right_pose = right.removeprefix("right_")
    if left_pose not in _LEFT_POSES or right_pose not in _RIGHT_POSES:
        raise ValueError(f"invalid chord {name!r}")
    return left_pose, right_pose


def validate_assignments(assignments: Mapping[str, str], commands: set[str]) -> dict[str, str]:
    """Keep only known chords mapped to allow-listed commands."""
    cleaned: dict[str, str] = {}
    for name, command in assignments.items():
        try:
            parse_chord(name)
        except ValueError:
            continue
        if command in commands:
            cleaned[name] = command
    return cleaned


class ChordEngine:
    def __init__(
        self,
        assignments: Mapping[str, str] | None = None,
        *,
        min_frames: int = 3,
        cooldown_s: float = 1.2,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.assignments = dict(assignments if assignments is not None else DEFAULT_CHORDS)
        self.min_frames = max(1, int(min_frames))
        self.cooldown_s = float(cooldown_s)
        self._clock = clock
        self._candidate: str | None = None
        self._frames = 0
        self._latched = False
        self._last_fired = float("-inf")

    def reset(self) -> None:
        self._candidate = None
        self._frames = 0
        self._latched = False
        self._last_fired = float("-inf")

    def update(
        self,
        left_pose: str | None,
        right_pose: str | None,
        now: float | None = None,
    ) -> ChordMatch | None:
        """Feed the two hand poses; returns a match on the frame it fires."""
        now = self._clock() if now is None else float(now)
        if not left_pose or not right_pose:
            self._candidate, self._frames, self._latched = None, 0, False
            return None

        name = f"left_{left_pose}+right_{right_pose}"
        if name != self._candidate:
            self._candidate = name
            self._frames = 1
            self._latched = False
        else:
            self._frames += 1

        command = self.assignments.get(name, "none")
        if self._latched or command == "none" or self._frames < self.min_frames:
            return None
        if now - self._last_fired < self.cooldown_s:
            return None
        self._latched = True
        self._last_fired = now
        return ChordMatch(name=name, command=command)
