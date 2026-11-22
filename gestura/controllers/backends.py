# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""OS input backends.

`PyAutoGuiBackend` is the real implementation (with Win32 overrides);
`RecordingBackend` records calls and is used by tests and test mode tooling.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Protocol

from ..core.safety_manager import FailSafeTriggered

log = logging.getLogger(__name__)


def _disable_mouseinfo_if_unusable() -> None:
    """PyAutoGUI imports `mouseinfo`, which needs tkinter and calls sys.exit()
    (Linux) or raises (Windows) without it. Gestura never uses mouseinfo, so
    when tkinter is missing we make the import fail cleanly; PyAutoGUI already
    handles ImportError for it."""
    if "mouseinfo" in sys.modules:
        return
    try:
        import tkinter  # noqa: F401
    except ImportError:
        sys.modules["mouseinfo"] = None  # type: ignore[assignment]  -> import raises ImportError


class InputBackend(Protocol):
    fractional_scroll: bool

    def screen_size(self) -> tuple[int, int]: ...
    def position(self) -> tuple[int, int]: ...
    def move_to(self, x: int, y: int) -> None: ...
    def click(self, button: str = "left", clicks: int = 1) -> None: ...
    def mouse_down(self, button: str = "left") -> None: ...
    def mouse_up(self, button: str = "left") -> None: ...
    def scroll(self, notches: float) -> None: ...
    def hscroll(self, notches: float) -> None: ...
    def press(self, key: str) -> None: ...
    def hotkey(self, *keys: str) -> None: ...
    def key_down(self, key: str) -> None: ...
    def key_up(self, key: str) -> None: ...
    def write_text(self, text: str) -> None: ...


class PyAutoGuiBackend:
    """Real OS input. PyAutoGUI is imported lazily (it needs a display)."""

    def __init__(self, failsafe: bool = True) -> None:
        _disable_mouseinfo_if_unusable()
        import pyautogui  # noqa: PLC0415 - lazy on purpose

        self._pg = pyautogui
        pyautogui.PAUSE = 0  # default 0.1 s sleep after every call would cap us at 10 FPS
        pyautogui.MINIMUM_DURATION = 0
        pyautogui.FAILSAFE = failsafe
        self._win = sys.platform == "win32"
        self.fractional_scroll = self._win
        self._lock = threading.Lock()

    def set_failsafe(self, on: bool) -> None:
        self._pg.FAILSAFE = on

    def _call(self, fn, *args, **kwargs):
        try:
            with self._lock:
                return fn(*args, **kwargs)
        except self._pg.FailSafeException as exc:
            raise FailSafeTriggered(str(exc)) from exc

    def screen_size(self) -> tuple[int, int]:
        w, h = self._pg.size()
        return int(w), int(h)

    def position(self) -> tuple[int, int]:
        x, y = self._pg.position()
        return int(x), int(y)

    def move_to(self, x: int, y: int) -> None:
        self._call(self._pg.moveTo, x, y, _pause=False)

    def click(self, button: str = "left", clicks: int = 1) -> None:
        self._call(self._pg.click, button=button, clicks=clicks, interval=0.0, _pause=False)

    def mouse_down(self, button: str = "left") -> None:
        self._call(self._pg.mouseDown, button=button, _pause=False)

    def mouse_up(self, button: str = "left") -> None:
        # Releasing a held button must never be blocked by the fail-safe.
        with self._lock:
            saved = self._pg.FAILSAFE
            self._pg.FAILSAFE = False
            try:
                self._pg.mouseUp(button=button, _pause=False)
            finally:
                self._pg.FAILSAFE = saved

    def scroll(self, notches: float) -> None:
        if self._win:
            from . import win32_input

            self._call(self._pg.failSafeCheck)
            win32_input.send_wheel(notches)
        else:
            self._call(self._pg.scroll, int(notches), _pause=False)

    def hscroll(self, notches: float) -> None:
        if self._win:
            from . import win32_input

            self._call(self._pg.failSafeCheck)
            win32_input.send_wheel(notches, horizontal=True)
        else:
            self._call(self._pg.hscroll, int(notches), _pause=False)

    def press(self, key: str) -> None:
        self._call(self._pg.press, key, _pause=False)

    def hotkey(self, *keys: str) -> None:
        self._call(self._pg.hotkey, *keys, interval=0.0, _pause=False)

    def key_down(self, key: str) -> None:
        self._call(self._pg.keyDown, key, _pause=False)

    def key_up(self, key: str) -> None:
        self._call(self._pg.keyUp, key, _pause=False)

    def write_text(self, text: str) -> None:
        if self._win:
            from . import win32_input

            self._call(self._pg.failSafeCheck)
            win32_input.send_text(text)
        else:
            # PyAutoGUI's write() only handles characters on the US layout.
            self._call(self._pg.write, text, interval=0.0, _pause=False)


class YdotoolBackend:
    """Wayland input through ``ydotool`` (experimental, opt-in, user service only).

    Wayland compositors do not accept XTest, so an X11 backend cannot inject
    input there. ``ydotool`` writes to ``/dev/uinput`` through its own daemon
    (``ydotoold``), which grants the kernel-level injection without running
    AIRDESK as root.

    This backend is **opt-in** (``AIRDESK_INPUT_BACKEND=ydotool``) and marked
    experimental in diagnostics: its command syntax differs between ydotool
    versions and it has not been validated on Kali hardware by this build.
    Pointer movement, buttons and keys are implemented; scrolling relies on the
    wheel button codes and is reported as unverified.
    """

    fractional_scroll = False
    experimental = True

    #: ydotool's button codes (its own mapping, not the kernel ``BTN_*`` values).
    _BUTTONS = {"left": "0xC0", "right": "0xC1", "middle": "0xC2"}
    _WHEEL_UP, _WHEEL_DOWN, _WHEEL_LEFT, _WHEEL_RIGHT = "0x04", "0x05", "0x06", "0x07"
    _KEYS = {
        "ctrl": "leftctrl", "alt": "leftalt", "shift": "leftshift", "win": "leftmeta",
        "esc": "esc", "escape": "esc", "enter": "enter", "return": "enter",
        "tab": "tab", "space": "space", "backspace": "backspace", "delete": "delete",
        "up": "up", "down": "down", "left": "left", "right": "right",
        "home": "home", "end": "end", "pageup": "pageup", "pagedown": "pagedown",
        "volumeup": "volumeup", "volumedown": "volumedown", "volumemute": "mute",
        "playpause": "playpause", "nexttrack": "nextsong", "prevtrack": "previoussong",
    }

    def __init__(self, *, runner=None, screen_size: tuple[int, int] | None = None) -> None:
        if not shutil.which("ydotool"):
            raise OSError("ydotool is not installed")
        self._screen = screen_size
        self._run_cmd = runner or self._default_run
        self._pos = (0, 0)

    @staticmethod
    def _default_run(argv: list[str]) -> int:
        try:
            return subprocess.run(  # noqa: S603 - fixed argv, no shell
                argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=5, check=False, stdin=subprocess.DEVNULL,
            ).returncode
        except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - host specific
            log.warning("ydotool failed: %s", exc)
            return 1

    def _cmd(self, *args: str) -> bool:
        return self._run_cmd(["ydotool", *args]) == 0

    # ydotool needs one process per event; keep it off the fast path.
    def screen_size(self) -> tuple[int, int]:
        if self._screen is None:
            try:
                from PySide6.QtGui import QGuiApplication

                screen = QGuiApplication.primaryScreen()
                self._screen = (screen.geometry().width(), screen.geometry().height()) \
                    if screen is not None else (1920, 1080)
            except Exception:  # noqa: BLE001 - headless
                self._screen = (1920, 1080)
        return self._screen

    def position(self) -> tuple[int, int]:
        return self._pos

    def move_to(self, x: int, y: int) -> None:
        self._pos = (int(x), int(y))
        self._cmd("mousemove", "--absolute", str(int(x)), str(int(y)))

    def click(self, button: str = "left", clicks: int = 1) -> None:
        code = self._BUTTONS.get(button, self._BUTTONS["left"])
        for _ in range(max(1, int(clicks))):
            self._cmd("click", code)

    def mouse_down(self, button: str = "left") -> None:
        self._cmd("mousedown", self._BUTTONS.get(button, self._BUTTONS["left"]))

    def mouse_up(self, button: str = "left") -> None:
        self._cmd("mouseup", self._BUTTONS.get(button, self._BUTTONS["left"]))

    def _wheel(self, code: str, notches: float) -> None:
        for _ in range(min(10, max(0, int(abs(notches))))):
            self._cmd("click", code)

    def scroll(self, notches: float) -> None:
        self._wheel(self._WHEEL_UP if notches > 0 else self._WHEEL_DOWN, notches)

    def hscroll(self, notches: float) -> None:
        self._wheel(self._WHEEL_RIGHT if notches > 0 else self._WHEEL_LEFT, notches)

    @classmethod
    def _key_name(cls, key: str) -> str:
        return cls._KEYS.get(key.lower(), key.lower())

    def press(self, key: str) -> None:
        self._cmd("key", self._key_name(key))

    def hotkey(self, *keys: str) -> None:
        self._cmd("key", "+".join(self._key_name(k) for k in keys))

    def key_down(self, key: str) -> None:
        self._cmd("key", f"{self._key_name(key)}:1")

    def key_up(self, key: str) -> None:
        self._cmd("key", f"{self._key_name(key)}:0")

    def write_text(self, text: str) -> None:
        self._cmd("type", text)


@dataclass(slots=True)
class InputCapabilities:
    """What the current session can actually inject (never assume X11)."""

    session: str
    name: str
    available: bool
    experimental: bool = False
    detail: str = ""
    pointer: bool = False
    keyboard: bool = False
    scroll: bool = False


def detect_input_capabilities(session: str | None = None) -> InputCapabilities:
    """Probe the input stack without creating a backend or moving the pointer."""
    from ..services.platform_diagnostics import detect_session

    session = session or detect_session()
    if sys.platform == "win32":
        return InputCapabilities(session, "Win32 SendInput (PyAutoGUI)", True,
                                 detail="native pointer + keyboard injection",
                                 pointer=True, keyboard=True, scroll=True)
    if session == "x11":
        import ctypes.util

        xtest = bool(ctypes.util.find_library("Xtst"))
        return InputCapabilities(
            session, "X11 XTest (PyAutoGUI)", xtest,
            detail="libXtst present" if xtest else "install libxtst6 for synthetic input",
            pointer=xtest, keyboard=xtest, scroll=xtest,
        )
    if session == "wayland":
        ydotool = bool(shutil.which("ydotool"))
        # `experimental` only applies when ydotool is actually there to try.
        return InputCapabilities(
            session, "ydotool (experimental)", ydotool, experimental=ydotool,
            detail=("ydotool found; requires `systemctl --user enable --now ydotool` and uinput access. "
                    "Unverified on this build." if ydotool else
                    "Wayland blocks XTest; install ydotool (opt-in via AIRDESK_INPUT_BACKEND=ydotool)"),
            pointer=ydotool, keyboard=ydotool, scroll=False,
        )
    return InputCapabilities(session, "none", False, detail="no graphical session detected")


def select_backend(failsafe: bool = True) -> tuple[InputBackend | None, str]:
    """Pick a real backend, returning (backend, error). Never raises.

    X11/Windows use PyAutoGUI. On Wayland nothing is picked automatically: the
    compositor rejects XTest, so a ydotool backend must be requested explicitly
    (``AIRDESK_INPUT_BACKEND=ydotool``) and is reported as experimental.
    """
    forced = os.environ.get("AIRDESK_INPUT_BACKEND", "").strip().lower()
    session = detect_input_capabilities().session
    if forced == "ydotool" or (forced == "auto" and session == "wayland"):
        try:
            return YdotoolBackend(), "ydotool backend is experimental and unverified"
        except OSError as exc:
            return None, f"ydotool requested but unavailable: {exc}"
    if session == "wayland":
        return None, ("Wayland session: synthetic input is blocked by the compositor. "
                      "Run an X11 session on Kali, or set AIRDESK_INPUT_BACKEND=ydotool "
                      "(experimental). Tracking and test mode still work.")
    try:
        return PyAutoGuiBackend(failsafe=failsafe), ""
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - e.g. no display
        return None, f"System input is unavailable ({exc}); running in simulation only."


class RecordingBackend:
    """Records every call instead of touching the OS."""

    def __init__(self, size: tuple[int, int] = (1920, 1080), fractional_scroll: bool = False) -> None:
        self.size = size
        self.fractional_scroll = fractional_scroll
        self.calls: list[tuple] = []
        self.pos = (size[0] // 2, size[1] // 2)

    def screen_size(self) -> tuple[int, int]:
        return self.size

    def position(self) -> tuple[int, int]:
        return self.pos

    def move_to(self, x: int, y: int) -> None:
        self.pos = (x, y)
        self.calls.append(("move_to", x, y))

    def click(self, button: str = "left", clicks: int = 1) -> None:
        self.calls.append(("click", button, clicks))

    def mouse_down(self, button: str = "left") -> None:
        self.calls.append(("mouse_down", button))

    def mouse_up(self, button: str = "left") -> None:
        self.calls.append(("mouse_up", button))

    def scroll(self, notches: float) -> None:
        self.calls.append(("scroll", notches))

    def hscroll(self, notches: float) -> None:
        self.calls.append(("hscroll", notches))

    def press(self, key: str) -> None:
        self.calls.append(("press", key))

    def hotkey(self, *keys: str) -> None:
        self.calls.append(("hotkey", *keys))

    def key_down(self, key: str) -> None:
        self.calls.append(("key_down", key))

    def key_up(self, key: str) -> None:
        self.calls.append(("key_up", key))

    def write_text(self, text: str) -> None:
        self.calls.append(("write_text", text))

    def named(self, name: str) -> list[tuple]:
        return [c for c in self.calls if c[0] == name]
