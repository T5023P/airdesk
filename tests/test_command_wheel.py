# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
"""AIR COMMAND radial wheel: selection, confirmation and cancellation."""

from __future__ import annotations

from gestura.core.air_commands import AIR_COMMAND_IDS
from gestura.core.command_wheel import CommandWheel


def make_wheel(**kwargs) -> CommandWheel:
    clock = [0.0]
    wheel = CommandWheel(clock=lambda: clock[0], **kwargs)
    wheel._test_clock = clock  # type: ignore[attr-defined]
    return wheel


def advance(wheel: CommandWheel, seconds: float) -> float:
    clock = wheel._test_clock  # type: ignore[attr-defined]
    clock[0] += seconds
    return clock[0]


def test_sector_zero_is_at_the_top_and_numbering_is_clockwise():
    wheel = CommandWheel()
    assert wheel.sector_of(0.5, 0.02) == 0
    assert wheel.sector_of(0.98, 0.5) == len(wheel.commands) // 4
    assert wheel.sector_of(0.5, 0.98) == len(wheel.commands) // 2
    assert wheel.sector_of(0.02, 0.5) == (3 * len(wheel.commands)) // 4


def test_dead_zone_selects_nothing():
    wheel = CommandWheel(dead_zone=0.15)
    assert wheel.sector_of(0.5, 0.5) is None
    assert wheel.command_at(0.5, 0.5) is None


def test_wheel_opens_only_after_the_hold():
    wheel = make_wheel(activation_hold_s=0.25)
    assert not wheel.update(activation=True, now=0.0).active
    assert not wheel.update(activation=True, now=0.20).active
    update = wheel.update(activation=True, now=0.30)
    assert update.just_opened and wheel.active and update.progress == 0.0


def test_hold_progress_is_reported_while_waiting():
    wheel = make_wheel(activation_hold_s=0.40)
    wheel.update(activation=True, now=0.0)
    assert 0.2 < wheel.update(activation=True, now=0.20).progress < 0.7


def test_pointer_selects_and_pinch_confirms():
    wheel = make_wheel(activation_hold_s=0.1)
    wheel.update(activation=True, now=0.0)
    wheel.update(activation=True, now=0.2)
    update = wheel.update(activation=False, pointer=(0.5, 0.1), now=0.3)
    assert update.selected == AIR_COMMAND_IDS[0]

    update = wheel.update(activation=False, pointer=(0.5, 0.1), confirm_closed=True, now=0.4)
    assert update.confirmed == AIR_COMMAND_IDS[0]
    assert update.just_closed and not wheel.active


def test_confirmation_needs_a_fresh_pinch():
    wheel = make_wheel(activation_hold_s=0.1, cooldown_s=0.0)
    wheel.update(activation=True, now=0.0)
    wheel.update(activation=True, now=0.2)
    wheel.update(activation=False, pointer=(0.5, 0.1), confirm_closed=True, now=0.4)
    # Re-open, keep the pinch closed: it must not confirm again until released.
    wheel.update(activation=True, now=0.5)
    wheel.update(activation=True, now=0.7)
    update = wheel.update(activation=False, pointer=(0.5, 0.1), confirm_closed=True, now=0.8)
    assert update.confirmed is None
    wheel.update(activation=False, pointer=(0.5, 0.1), confirm_closed=False, now=0.9)
    update = wheel.update(activation=False, pointer=(0.5, 0.1), confirm_closed=True, now=1.0)
    assert update.confirmed == AIR_COMMAND_IDS[0]


def test_open_palm_cancels_without_a_command():
    wheel = make_wheel(activation_hold_s=0.1, cancel_hold_s=0.3)
    wheel.update(activation=True, now=0.0)
    wheel.update(activation=True, now=0.2)
    wheel.update(activation=False, pointer=(0.5, 0.1), cancel=True, now=1.0)
    assert wheel.active  # not yet: cancel needs its hold
    update = wheel.update(activation=False, pointer=(0.5, 0.1), cancel=True, now=1.35)
    assert update.cancelled and update.just_closed and not wheel.active
    assert update.confirmed is None


def test_cancel_is_ignored_during_the_first_300ms():
    wheel = make_wheel(activation_hold_s=0.05, cancel_hold_s=0.1)
    wheel.update(activation=True, now=0.0)
    wheel.update(activation=True, now=0.1)
    update = wheel.update(activation=False, cancel=True, now=0.2)
    assert not update.cancelled and wheel.active


def test_cooldown_blocks_immediate_reopen():
    wheel = make_wheel(activation_hold_s=0.05, cooldown_s=1.0)
    wheel.update(activation=True, now=0.0)
    wheel.update(activation=True, now=0.1)
    wheel.update(activation=False, pointer=(0.5, 0.1), confirm_closed=True, now=0.2)
    wheel.update(activation=True, now=0.3)
    assert not wheel.update(activation=True, now=0.9).active
    wheel.update(activation=True, now=1.3)
    assert wheel.update(activation=True, now=1.4).active


def test_close_is_idempotent_and_clears_selection():
    wheel = make_wheel(activation_hold_s=0.05)
    wheel.update(activation=True, now=0.0)
    wheel.update(activation=True, now=0.1)
    wheel.update(activation=False, pointer=(0.5, 0.1), now=0.2)
    assert wheel.selected is not None
    wheel.close()
    wheel.close()
    assert wheel.selected is None and not wheel.active


def test_wheel_rejects_an_empty_command_list():
    import pytest

    with pytest.raises(ValueError):
        CommandWheel(commands=())
