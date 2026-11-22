# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Application controller: wires every layer together.

    vision ─▶ gestures ─▶ CommandEngine ─(SafetyManager)─▶ controllers ─▶ OS
                                       ▲
    UI ─────── GesturaApp (this) ──────┘   (UI never calls controllers directly)
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QTimer, Signal

from ..config.settings import HandGesture, Settings
from ..controllers import register_executors
from ..controllers.air_actions import AirActionRunner
from ..controllers.backends import InputBackend, RecordingBackend, select_backend
from ..controllers.keyboard_controller import KeyboardController
from ..controllers.mouse_controller import MouseController
from ..controllers.navigation_controller import NavigationController
from ..core.command_engine import CommandEngine
from ..core.event_bus import EventBus
from ..core.safety_manager import EngineState, SafetyManager
from ..macros.model import Macro
from ..macros.runner import MacroRunner, RunResult
from ..macros.store import MacroStore
from ..services.audio_service import AudioService
from ..services.configuration_service import ConfigurationService
from ..services.display_service import enumerate_displays
from ..services.hotkey_service import GlobalHotkey
from ..services.tracking_service import TrackingService

log = logging.getLogger(__name__)


class GesturaApp(QObject):
    state_changed = Signal()  # safety state / test mode changed (always on GUI thread)
    settings_changed = Signal(object)  # Settings
    keyboard_toggle_requested = Signal()
    screenshot_requested = Signal()
    macros_changed = Signal()
    notice = Signal(str)

    def __init__(self, config: ConfigurationService, source_spec: str | None = None,
                 force_test_mode: bool | None = None, backend: InputBackend | None = None) -> None:
        super().__init__()
        self.config = config
        self.settings: Settings = config.load()
        test_mode = self.settings.safety.start_in_test_mode if force_test_mode is None else force_test_mode
        self.safety = SafetyManager(test_mode=test_mode,
                                    confirm_sensitive=self.settings.safety.confirm_sensitive,
                                    confirm_window_s=self.settings.safety.confirm_window_ms / 1000)
        self.bus = EventBus()
        self.commands = CommandEngine(self.safety, self.bus)
        self.commands.set_mapping(self._mapping())

        self.backend_error = ""
        if backend is None:
            # Session-aware selection: Windows/X11 -> PyAutoGUI (SendInput/XTest),
            # Wayland -> nothing automatic (the compositor blocks XTest), so the
            # app degrades to simulation and says so instead of failing silently.
            backend, self.backend_error = select_backend(
                failsafe=self.settings.safety.pyautogui_failsafe)
            if backend is None:
                log.warning(self.backend_error)
                backend = RecordingBackend()
        self.backend = backend
        self.keyboard = KeyboardController(backend)
        # Audio is platform-adaptive: Windows multimedia keys, Linux wpctl/pactl
        # when present (never a hard dependency, never root).
        self.audio = AudioService(press_key=self.keyboard.press)
        self.displays = enumerate_displays()
        self.mouse = MouseController(backend, self.settings.cursor, lambda: self.displays)
        self.mouse.refresh_displays(self.settings.display.monitor)
        self.nav = NavigationController(self.keyboard)

        # ---- AIR MACROS store + runner (allow-listed actions only)
        self.macros_store = MacroStore(self.settings.macros.path or None)
        self.macro_book = self.macros_store.load()
        if self.macros_store.error:
            log.warning(self.macros_store.error)
        self.macro_runner = MacroRunner(self._dispatch_macro_action)

        # ---- AIR COMMAND executor (shared by the wheel, chords and macros)
        self.air = AirActionRunner(
            keyboard=self.keyboard,
            mouse=self.mouse,
            switch_mode=self.switch_mode,
            toggle_keyboard=self.keyboard_toggle_requested.emit,
            toggle_pause=lambda: self.safety.toggle_pause("air command"),
            screenshot=self.request_screenshot,
            is_test_mode=lambda: self.safety.test_mode,
            audio=self.audio,
        )

        register_executors(self.commands, self.mouse, self.keyboard, self.nav, {
            "app.toggle_pause": lambda: self.safety.toggle_pause("open palm"),
            "app.emergency_stop": lambda: self.safety.emergency_stop("emergency gesture"),
            "app.toggle_keyboard": self.keyboard_toggle_requested.emit,
            "app.open_browser": lambda: self.air.run_command("app.open_browser"),
            "app.open_calculator": lambda: self.air.run_command("app.open_calculator"),
            "app.open_file_manager": lambda: self.air.run_command("app.open_file_manager"),
            "app.screenshot": lambda: self.air.run_command("app.screenshot"),
            "mode.air_mouse": lambda: self.switch_mode("air_mouse"),
            "mode.air_keyboard": lambda: self.switch_mode("air_keyboard"),
            "mode.presentation": lambda: self.switch_mode("presentation"),
            # Media keys go through the audio service so Linux uses the real
            # mixer (wpctl/pactl) instead of blind X11 keysyms.
            "media.volume_up": lambda: self.audio.change("up"),
            "media.volume_down": lambda: self.audio.change("down"),
            "media.mute": lambda: self.audio.toggle_mute(),
        })

        self.tracking = TrackingService(
            self.settings, self.safety, self.commands, self.bus, source_spec,
            air=self.air, macros=lambda: self.macro_book.macros,
            macro_runner=self.macro_runner,
        )
        # Safety listeners may fire on the worker thread (palm gesture, fail-safe):
        # re-emit through a queued signal so all UI work happens on the GUI thread.
        self._safety_signal_relay = _Relay()
        self._safety_signal_relay.fired.connect(self._on_safety_changed)
        self.safety.add_listener(lambda _s: self._safety_signal_relay.fired.emit())
        self.tracking.running_changed.connect(lambda _r: self.state_changed.emit())

        self.hotkey = GlobalHotkey(lambda: self._safety_signal_relay.hotkey.emit())
        self._safety_signal_relay.hotkey.connect(lambda: self.emergency_stop("global hotkey"))
        if self.settings.safety.global_hotkey:
            self.hotkey.start()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._save_now)

    # --------------------------------------------------------------- control
    def start(self) -> None:
        if self.safety.state == EngineState.EMERGENCY:
            self.notice.emit("Clear the emergency stop first.")
            return
        self.tracking.start()
        self.safety.start()

    def stop(self) -> None:
        self.safety.stop()
        self.tracking.stop()
        self._release_inputs()

    def emergency_stop(self, reason: str = "emergency stop button") -> None:
        self.safety.emergency_stop(reason)  # blocks commands immediately (thread-safe)
        self._release_inputs()
        self.tracking.stop()

    def clear_emergency(self) -> None:
        self.safety.clear_emergency()

    def toggle_pause(self) -> None:
        self.safety.toggle_pause("button")

    def set_test_mode(self, on: bool) -> None:
        self.safety.set_test_mode(on)

    def _release_inputs(self) -> None:
        self.mouse.release_buttons()
        self.keyboard.release_all()
        self.mouse.reset()

    def _on_safety_changed(self) -> None:
        if self.safety.state in (EngineState.EMERGENCY, EngineState.PAUSED, EngineState.STOPPED):
            self._release_inputs()
        if self.safety.state == EngineState.EMERGENCY and self.tracking.running:
            self.tracking.stop()
        self.state_changed.emit()

    # ------------------------------------------------------- AIR COMMAND / macros
    def switch_mode(self, name: str) -> str:
        """Apply one of AIRDESK's modes. Returns a short feedback message."""
        s = self.settings.copy_deep()
        if name == "air_mouse":
            s.modes.mouse, s.modes.keyboard, s.modes.presentation = True, False, False
        elif name == "air_keyboard":
            s.modes.mouse, s.modes.keyboard, s.modes.presentation = True, True, False
        elif name == "presentation":
            s.modes.mouse, s.modes.keyboard, s.modes.presentation = True, False, True
        elif name in ("mouse", "keyboard", "navigation"):
            setattr(s.modes, name, True)
        else:
            return f"Unknown mode {name}"
        self.update_settings(s)
        return f"Mode → {name.replace('_', ' ').upper()}"

    def request_screenshot(self) -> str:
        """Ask the GUI thread to grab the screen (Qt is not thread-safe)."""
        self.screenshot_requested.emit()
        return "Screenshot captured"

    def _dispatch_macro_action(self, action) -> str:
        return self.air.run_action(action)

    def save_macros(self, book) -> None:
        self.macro_book = book
        try:
            self.macros_store.save(book)
        except OSError as exc:
            self.notice.emit(f"Could not save macros: {exc}")
            return
        self.macros_changed.emit()

    def reload_macros(self) -> None:
        self.macro_book = self.macros_store.load()
        self.macros_changed.emit()

    def run_macro(self, macro: Macro, confirmed: bool = False) -> RunResult:
        return self.macro_runner.run(macro, confirmed=confirmed)

    @property
    def active_mode(self) -> str:
        m = self.settings.modes
        if m.presentation:
            return "PRESENTATION"
        if m.keyboard:
            return "AIR KEYBOARD"
        if m.navigation:
            return "NAVIGATION"
        if m.mouse:
            return "AIR MOUSE"
        return "IDLE"

    # -------------------------------------------------------------- settings
    def _mapping(self) -> dict[str, str]:
        mapping = {**self.settings.mappings.hand, **self.settings.mappings.head}
        if self.settings.modes.presentation:
            # Presentation mode: palm swipes page through slides instead of tabs.
            mapping[HandGesture.SWIPE_LEFT.value] = "browser.page_up"
            mapping[HandGesture.SWIPE_RIGHT.value] = "browser.page_down"
        return mapping

    def update_settings(self, settings: Settings, save: bool = True) -> None:
        if settings.startup.launch_at_login != self.settings.startup.launch_at_login:
            from ..services import startup_service

            if startup_service.is_packaged():
                if settings.startup.launch_at_login:
                    self.notice.emit(startup_service.PACKAGED_STARTUP_HINT)
            elif startup_service.is_supported() and not startup_service.set_enabled(
                    settings.startup.launch_at_login):
                self.notice.emit("Could not change the launch-at-login setting.")
        self.settings = settings
        self.mouse.settings = settings.cursor
        self.displays = enumerate_displays()
        self.mouse.refresh_displays(settings.display.monitor)
        self.safety.confirm_sensitive = settings.safety.confirm_sensitive
        self.safety.confirm_window_s = settings.safety.confirm_window_ms / 1000
        if hasattr(self.backend, "set_failsafe"):
            self.backend.set_failsafe(settings.safety.pyautogui_failsafe)
        self.commands.set_mapping(self._mapping())
        self.tracking.apply_settings(settings)
        self.settings_changed.emit(settings)
        if save:
            self._save_timer.start()

    def set_mode(self, mode: str, on: bool) -> None:
        s = self.settings.copy_deep()
        setattr(s.modes, mode, on)
        self.update_settings(s)

    def _save_now(self) -> None:
        try:
            self.config.save(self.settings)
        except OSError as exc:
            self.notice.emit(f"Could not save settings: {exc}")

    def shutdown(self) -> None:
        self.stop()
        self.hotkey.stop()
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save_now()


class _Relay(QObject):
    fired = Signal()
    hotkey = Signal()
