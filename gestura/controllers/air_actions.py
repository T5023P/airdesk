# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Executor for AIR COMMAND wheel entries and AIR MACROS actions.

Everything here is allow-listed by construction:

* application launches use fixed argv lists (``shell=False``, no user string),
* shortcuts come from ``macros.model.ALLOWED_SHORTCUTS``,
* mode switches go through the application's own settings,
* nothing accepts a command line, a path or an arbitrary key combination.

Test mode short-circuits every OS-visible action, so the wheel and macros can be
demonstrated without touching the desktop.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Callable

from ..core.air_commands import AIR_COMMAND_BY_ID
from ..macros.model import ALLOWED_SHORTCUTS, MacroAction

log = logging.getLogger(__name__)

# Linux launchers, tried in order. Never taken from user input.
_CALCULATORS = ("gnome-calculator", "kcalc", "galculator", "xcalc")
_FILE_MANAGERS = ("xdg-open", "thunar", "nautilus", "dolphin")


class AirActionRunner:
    def __init__(
        self,
        *,
        keyboard,
        mouse,
        switch_mode: Callable[[str], str],
        toggle_keyboard: Callable[[], None],
        toggle_pause: Callable[[], None],
        screenshot: Callable[[], str],
        is_test_mode: Callable[[], bool] | None = None,
        audio=None,
    ) -> None:
        self._keyboard = keyboard
        self._mouse = mouse
        self._switch_mode = switch_mode
        self._toggle_keyboard = toggle_keyboard
        self._toggle_pause = toggle_pause
        self._screenshot = screenshot
        self._is_test_mode = is_test_mode or (lambda: False)
        # Optional AudioService: on Linux it drives wpctl/pactl instead of keysyms.
        self._audio = audio

    # ------------------------------------------------------------------ guard
    def _blocked(self) -> str | None:
        return "Test mode — not executed" if self._is_test_mode() else None

    def release_inputs(self) -> None:
        """Called when the wheel opens: nothing may stay pressed underneath it."""
        try:
            self._mouse.release_buttons()
        except Exception:  # noqa: BLE001
            log.debug("release_buttons failed", exc_info=True)

    # ------------------------------------------------------------- launching
    @staticmethod
    def _spawn(argv: list[str]) -> str:
        subprocess.Popen(  # noqa: S603 - fixed argv, no shell, no user input
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            close_fds=True,
        )
        return f"Launched {Path(argv[0]).name}"

    def _launch(self, app_id: str) -> str:
        if app_id == "browser":
            opened = webbrowser.open("about:blank", new=1)
            return "Opened the browser" if opened else "No default browser found"
        if app_id == "calculator":
            if sys.platform == "win32":
                return self._spawn(["calc.exe"])
            for name in _CALCULATORS:
                path = shutil.which(name)
                if path:
                    return self._spawn([path])
            return "No calculator found (install gnome-calculator or kcalc)"
        if app_id == "file_manager":
            if sys.platform == "win32":
                return self._spawn(["explorer.exe"])
            opener = shutil.which("xdg-open")
            if opener:
                return self._spawn([opener, str(Path.home())])
            for name in _FILE_MANAGERS:
                path = shutil.which(name)
                if path:
                    return self._spawn([path, str(Path.home())])
            return "No file manager found"
        return f"Unknown app {app_id}"

    # -------------------------------------------------------------- commands
    def run_command(self, command_id: str) -> str:
        """Execute one AIR COMMAND id; returns a short human-readable result."""
        spec = AIR_COMMAND_BY_ID.get(command_id)
        if spec is None:
            return f"Blocked unknown command {command_id}"

        if command_id == "app.toggle_pause":
            self._toggle_pause()  # app control is allowed even in test mode
            return "Toggled pause"
        if command_id.startswith("mode."):
            return self._switch_mode(command_id.removeprefix("mode."))
        if command_id == "app.toggle_keyboard":
            self._toggle_keyboard()
            return "Toggled the virtual keyboard"

        blocked = self._blocked()
        if blocked:
            return f"{spec.label}: {blocked}"

        if command_id == "app.open_browser":
            return self._launch("browser")
        if command_id == "app.open_calculator":
            return self._launch("calculator")
        if command_id == "app.open_file_manager":
            return self._launch("file_manager")
        if command_id == "app.screenshot":
            return self._screenshot()
        if command_id == "media.volume_up":
            if self._audio is not None:
                return self._audio.change("up")
            self._keyboard.press("volumeup")
            return "Volume up"
        if command_id == "media.volume_down":
            if self._audio is not None:
                return self._audio.change("down")
            self._keyboard.press("volumedown")
            return "Volume down"
        if command_id == "media.play_pause":
            self._keyboard.press("playpause")
            return "Play / pause"
        return f"No executor for {spec.label}"

    # --------------------------------------------------------------- macros
    def run_action(self, action: MacroAction) -> str:
        if action.type == "open_app":
            blocked = self._blocked()
            return f"{action.describe()}: {blocked}" if blocked else self._launch(action.target)
        if action.type == "shortcut":
            combo = action.target
            if combo not in ALLOWED_SHORTCUTS:
                return "Blocked: shortcut not allow-listed"
            blocked = self._blocked()
            if blocked:
                return f"{action.describe()}: {blocked}"
            self._keyboard.hotkey(*combo.split("+"))
            return action.describe()
        if action.type == "set_mode":
            return self._switch_mode(action.target)
        if action.type == "keyboard":
            self._toggle_keyboard()
            return "Toggled the virtual keyboard"
        if action.type == "volume":
            mapping = {"up": "volumeup", "down": "volumedown", "mute": "volumemute"}
            blocked = self._blocked()
            if blocked:
                return f"{action.describe()}: {blocked}"
            if self._audio is not None:
                if action.target == "mute":
                    return self._audio.toggle_mute()
                return self._audio.change(action.target)
            self._keyboard.press(mapping[action.target])
            return action.describe()
        if action.type == "presentation":
            blocked = self._blocked()
            if blocked:
                return f"{action.describe()}: {blocked}"
            self._keyboard.press("pagedown" if action.target == "next" else "pageup")
            return action.describe()
        if action.type == "air_command":
            return self.run_command(action.target)
        if action.type == "wait":
            return f"Waited {action.delay_ms} ms"
        return "Blocked: unsupported action"
