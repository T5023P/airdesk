# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
"""AIR MACROS: validation, persistence and execution order."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from gestura.macros.model import (
    ALLOWED_TRIGGERS,
    Macro,
    MacroAction,
    MacroBook,
    new_action,
    new_macro,
)
from gestura.macros.runner import MacroRunner
from gestura.macros.store import MacroStore


def test_new_macro_is_valid_and_uses_an_allow_listed_command():
    macro = new_macro("Demo")
    assert macro.enabled and macro.actions
    assert macro.actions[0].target == "app.open_calculator"


@pytest.mark.parametrize(
    ("kind", "target"),
    [
        ("open_app", "terminal"),
        ("open_app", "/bin/sh"),
        ("open_app", "calc.exe"),
        ("shortcut", "rm -rf /"),
        ("shortcut", "ctrl+alt+delete"),
        ("shortcut", "ctrl+c; shutdown"),
        ("set_mode", "root"),
        ("volume", "max"),
        ("presentation", "random"),
        ("air_command", "app.toggle_pause; reboot"),
        ("air_command", "unknown.command"),
    ],
)
def test_actions_reject_anything_outside_the_allow_list(kind, target):
    with pytest.raises(ValidationError):
        MacroAction(type=kind, target=target)


def test_wait_needs_a_delay():
    with pytest.raises(ValidationError):
        MacroAction(type="wait", delay_ms=0)
    assert MacroAction(type="wait", delay_ms=500).delay_ms == 500


def test_macro_needs_actions_and_a_known_trigger():
    with pytest.raises(ValidationError):
        Macro(name="Empty", gesture="hand.pinch", actions=[])
    with pytest.raises(ValidationError):
        Macro(name="Bad", gesture="hand.explode", actions=[new_action("keyboard")])


def test_every_allowed_trigger_is_usable():
    for trigger in ALLOWED_TRIGGERS:
        macro = Macro(name="X", gesture=trigger, actions=[new_action("keyboard")])
        assert macro.gesture == trigger


def test_store_roundtrip(tmp_path):
    store = MacroStore(tmp_path / "macros.json")
    book = MacroBook(macros=[new_macro("One"), new_macro("Two")])
    store.save(book)
    loaded = store.load()
    assert [m.name for m in loaded.macros] == ["One", "Two"]
    assert store.error == ""


def test_store_quarantines_corrupt_files(tmp_path):
    path = tmp_path / "macros.json"
    path.write_text("{not json", encoding="utf-8")
    store = MacroStore(path)
    book = store.load()
    assert book.macros == []
    assert "invalid" in store.error
    assert not path.exists()
    assert list(tmp_path.glob("macros.invalid-*.json"))


def test_store_rejects_hand_edited_shell_actions(tmp_path):
    path = tmp_path / "macros.json"
    path.write_text(json.dumps({
        "version": 1,
        "macros": [{
            "id": "abc", "name": "Evil", "gesture": "hand.pinch",
            "actions": [{"type": "shortcut", "target": "rm -rf /", "delay_ms": 0}],
        }],
    }), encoding="utf-8")
    store = MacroStore(path)
    assert store.load().macros == []
    assert "invalid" in store.error


def test_runner_executes_in_order_with_delays():
    calls: list[str] = []
    sleeps: list[float] = []
    clock = [0.0]

    def dispatch(action):
        calls.append(f"{action.type}:{action.target}")
        return f"ran {action.target}"

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    runner = MacroRunner(dispatch, sleep=sleep, clock=lambda: clock[0])
    macro = Macro(name="M", gesture="hand.pinch", actions=[
        new_action("open_app", "calculator", 100),
        new_action("shortcut", "ctrl+s", 250),
        new_action("volume", "up", 0),
    ])
    result = runner.run(macro)
    assert result.ok
    assert calls == ["open_app:calculator", "shortcut:ctrl+s", "volume:up"]
    assert sleeps == [0.1, 0.25]
    assert len(result.lines) == 3


def test_runner_requires_confirmation_when_flagged():
    calls: list[str] = []
    runner = MacroRunner(lambda a: calls.append(a.target) or "ok")
    macro = Macro(name="M", gesture="hand.pinch", confirm=True,
                  actions=[new_action("open_app", "calculator")])
    result = runner.run(macro)
    assert result.needs_confirmation and not result.ok
    assert calls == []


def test_runner_skips_disabled_macros():
    runner = MacroRunner(lambda a: "ok")
    macro = Macro(name="Off", gesture="hand.pinch", enabled=False,
                  actions=[new_action("keyboard")])
    assert not runner.run(macro).ok


def test_runner_stops_after_a_failing_step():
    def dispatch(action):
        if action.type == "volume":
            raise RuntimeError("no audio device")
        return "ok"

    macro = Macro(name="M", gesture="hand.pinch", actions=[
        new_action("keyboard"), new_action("volume", "up"), new_action("keyboard"),
    ])
    result = MacroRunner(dispatch).run(macro)
    assert not result.ok
    assert "no audio device" in result.lines[-1]
    assert len(result.lines) == 2


def test_runner_aborts_when_the_budget_is_exceeded():
    clock = [0.0]

    def dispatch(action):
        clock[0] += 20.0
        return "ok"

    macro = Macro(name="Slow", gesture="hand.pinch", actions=[
        new_action("keyboard"), new_action("keyboard"), new_action("keyboard"),
    ])
    result = MacroRunner(dispatch, sleep=lambda s: None, clock=lambda: clock[0]).run(macro)
    assert not result.ok
    assert "too long" in result.lines[-1]
