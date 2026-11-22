# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
"""Multi-monitor geometry and cursor mapping."""

from __future__ import annotations

import pytest

from gestura.config.settings import CursorSettings
from gestura.controllers.mouse_controller import MouseController
from gestura.services.display_service import (
    Display,
    clamp_to_display,
    map_normalized,
    select_display,
)

PRIMARY = Display(0, "eDP-1", 0, 0, 1920, 1080, True)
LEFT = Display(1, "HDMI-1", -1920, 0, 1920, 1080, False)
RIGHT = Display(2, "DP-1", 1920, 0, 2560, 1440, False)


def test_map_normalized_uses_the_display_origin():
    x, y = map_normalized(0.0, 0.0, PRIMARY)
    assert (x, y) == (1, 1)
    x, y = map_normalized(1.0, 1.0, PRIMARY)
    assert x >= 1917 and y >= 1077


def test_map_normalized_supports_negative_coordinates():
    x, _ = map_normalized(0.0, 0.5, LEFT)
    assert x == -1919
    x, _ = map_normalized(1.0, 0.5, LEFT)
    assert x < 0


def test_map_normalized_is_clamped_for_out_of_range_input():
    assert map_normalized(-5.0, -5.0, PRIMARY) == map_normalized(0.0, 0.0, PRIMARY)
    assert map_normalized(9.0, 9.0, PRIMARY) == map_normalized(1.0, 1.0, PRIMARY)


def test_map_normalized_rejects_degenerate_display():
    with pytest.raises(ValueError):
        map_normalized(0.5, 0.5, Display(0, "broken", 0, 0, 0, 0))


def test_select_display_falls_back_to_primary_then_first():
    displays = [PRIMARY, RIGHT]
    assert select_display(displays, 1) is RIGHT
    assert select_display(displays, 99) is PRIMARY
    assert select_display([Display(0, "x", 0, 0, 800, 600)], 5).width == 800
    assert select_display([], 0) is None


def test_clamp_to_display():
    assert clamp_to_display(-5000, 5000, RIGHT) == (1920, 1439)
    assert clamp_to_display(99999, -99999, RIGHT) == (4479, 0)


class FakeBackend:
    fractional_scroll = False

    def __init__(self) -> None:
        self.moves: list[tuple[int, int]] = []

    def screen_size(self) -> tuple[int, int]:
        return 1920, 1080

    def move_to(self, x: int, y: int) -> None:
        self.moves.append((x, y))

    def click(self, *a, **k) -> None: ...
    def mouse_down(self, *a, **k) -> None: ...
    def mouse_up(self, *a, **k) -> None: ...
    def scroll(self, *a, **k) -> None: ...
    def hscroll(self, *a, **k) -> None: ...
    def position(self) -> tuple[int, int]:
        return self.moves[-1] if self.moves else (0, 0)


def make_mouse(displays):
    backend = FakeBackend()
    mouse = MouseController(backend, CursorSettings(), lambda: displays)
    mouse.refresh_displays(0)
    return mouse, backend


def test_controller_maps_onto_the_selected_display():
    mouse, backend = make_mouse([PRIMARY, RIGHT])
    assert mouse.to_pixels(0.0, 0.0) == (1, 1)
    mouse.select_display_index(1)
    x, y = mouse.to_pixels(0.0, 0.0)
    assert x == 1921


def test_controller_without_display_provider_keeps_primary_behaviour():
    backend = FakeBackend()
    mouse = MouseController(backend, CursorSettings())
    assert mouse.to_pixels(0.0, 0.0) == (1, 1)
    assert mouse.to_pixels(1.0, 1.0) == (1918, 1078)


def test_display_switch_glides_instead_of_jumping():
    mouse, backend = make_mouse([PRIMARY, RIGHT])
    mouse.move_normalized(0.0, 0.0)  # somewhere on the primary
    mouse.select_display_index(1, settle_px=140)
    mouse._last = (500, 300)  # simulate a cursor position on the primary
    mouse.move_normalized(1.0, 1.0)  # far corner of the right display
    x, y = backend.moves[-1]
    assert abs(x - 500) <= 140 and abs(y - 300) <= 140


def test_display_switch_settles_after_a_few_moves():
    mouse, backend = make_mouse([PRIMARY, RIGHT])
    mouse.select_display_index(1, settle_px=140)
    mouse._last = (0, 0)
    for _ in range(40):
        mouse.move_normalized(1.0, 1.0)
    assert not mouse._settling
    assert backend.moves[-1][0] > 4300
