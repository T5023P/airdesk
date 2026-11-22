# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
"""Platform portability tests (mocked — they do not prove Kali hardware works).

Everything here is a unit test with injected tools, sessions and fake cameras.
Actual device behaviour must be verified with `scripts/bootstrap_kali.sh` and
`airdesk --full-diagnostics --probe-camera` on the target machine.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from gestura.controllers.air_actions import AirActionRunner
from gestura.controllers.backends import (
    RecordingBackend,
    YdotoolBackend,
    detect_input_capabilities,
    select_backend,
)
from gestura.controllers.keyboard_controller import KeyboardController
from gestura.controllers.mouse_controller import MouseController
from gestura.config.settings import CursorSettings
from gestura.services import platform_diagnostics as diag
from gestura.services.audio_service import AudioService
from gestura.vision import models
from gestura.vision.camera_diagnostics import (
    collect_camera_report,
    format_camera_report,
    probe_camera,
)

# --------------------------------------------------------------------------- helpers
def completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# --------------------------------------------------------------------------- session
def test_detect_session_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert diag.detect_session() == "windows"


def test_detect_session_prefers_xdg(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("DISPLAY", ":0")
    assert diag.detect_session() == "wayland"


def test_detect_session_falls_back_to_display(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    assert diag.detect_session() == "x11"


def test_detect_session_unknown_without_display(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    for name in ("XDG_SESSION_TYPE", "WAYLAND_DISPLAY", "DISPLAY"):
        monkeypatch.delenv(name, raising=False)
    assert diag.detect_session() == "unknown"


def test_platform_report_is_json_serialisable(monkeypatch):
    import json

    report = diag.collect_report()
    payload = json.loads(diag.format_report(report, as_json=True))
    assert {"platform", "session", "capabilities"} <= set(payload)
    assert "AIRDESK platform diagnostics" in diag.format_report(report)


# --------------------------------------------------------------------------- models
def test_bundled_models_resolve_and_match_checksums():
    checks = models.verify_models()
    assert [c.name for c in checks] == [models.HAND_MODEL, models.FACE_MODEL]
    for check in checks:
        assert check.present, check.detail
        assert check.hash_ok is True, check.detail
        assert check.path.is_absolute() and check.path.is_file()


def test_model_paths_are_relative_to_the_package_not_the_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert models.model_dir().is_dir()
    assert models.model_path(models.HAND_MODEL).is_file()


def test_missing_model_is_reported_without_raising(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "model_dir", lambda: tmp_path / "models")
    check = models.verify_model(models.HAND_MODEL)
    assert check.present is False and check.usable is False
    assert "download_models" in check.detail
    assert models.models_ready() is False


def test_model_checksum_mismatch_is_detected(tmp_path, monkeypatch):
    fake = tmp_path / "models"
    fake.mkdir()
    (fake / models.HAND_MODEL).write_bytes(b"not the real model")
    monkeypatch.setattr(models, "model_dir", lambda: fake)
    check = models.verify_model(models.HAND_MODEL)
    assert check.present is True and check.hash_ok is False
    assert "checksum" in check.detail.lower()


# --------------------------------------------------------------------------- camera
class FakeSource:
    """Stands in for CameraSource with controllable behaviour."""

    def __init__(self, *, opens: bool = True, frames: int = 3, size=(320, 240),
                 raise_on_read: bool = False) -> None:
        self.opens, self.frames, self.size = opens, frames, size
        self.raise_on_read = raise_on_read
        self.frame_size = size if opens else (0, 0)
        self.released = 0
        self.reads = 0

    def open(self) -> bool:
        return self.opens

    def read(self):
        if self.raise_on_read:
            raise RuntimeError("camera unplugged")
        if self.reads >= self.frames:
            return None
        self.reads += 1
        return np.zeros((self.size[1], self.size[0], 3), dtype=np.uint8)

    def release(self) -> None:
        self.released += 1


def test_camera_probe_reports_measured_stream():
    source = FakeSource(frames=5)
    probe = probe_camera(0, seconds=0.2, source_factory=lambda **_: source)
    assert probe.opened and probe.working
    assert probe.width == 320 and probe.height == 240
    assert probe.measured_fps > 0
    assert source.released == 1, "the camera must always be released"


def test_camera_probe_reports_unavailable_device():
    source = FakeSource(opens=False)
    probe = probe_camera(7, seconds=0.1, source_factory=lambda **_: source)
    assert probe.opened is False and probe.working is False
    assert "video7" in probe.error or "camera 7" in probe.error.lower()
    assert source.released == 1


def test_camera_open_but_no_frames_is_a_failure():
    probe = probe_camera(0, seconds=0.2, source_factory=lambda **_: FakeSource(frames=0))
    assert probe.opened is True
    assert probe.working is False
    assert "no frames" in probe.error


def test_camera_probe_never_raises_on_driver_error():
    probe = probe_camera(0, seconds=0.1, source_factory=lambda **_: FakeSource(raise_on_read=True))
    assert probe.working is False
    assert "camera unplugged" in probe.error


def test_camera_report_without_camera_is_explicit():
    report = collect_camera_report(index=2, seconds=0.1,
                                   source_factory=lambda **_: FakeSource(opens=False))
    assert report.working_cameras == []
    assert report.selected_index == 2
    text = format_camera_report(report)
    assert "NOT AVAILABLE" in text
    assert "selected camera index: 2" in text


def test_camera_report_json_shape():
    import json

    report = collect_camera_report(index=0, seconds=0.1,
                                   source_factory=lambda **_: FakeSource(frames=2))
    payload = json.loads(format_camera_report(report, as_json=True))
    assert payload["cameras"][0]["working"] is True
    assert payload["selected_index"] == 0


def test_camera_source_release_is_idempotent_and_clears_size():
    from gestura.vision.camera_manager import CameraSource

    source = CameraSource(0)
    source.frame_size = (640, 480)
    source.release()
    source.release()
    assert source.frame_size == (0, 0)
    assert source._cap is None


# --------------------------------------------------------------------------- audio
def test_audio_detects_wpctl_first():
    audio = AudioService(platform="linux", which=lambda name: "/usr/bin/wpctl" if name == "wpctl" else None)
    assert audio.backend == "wpctl" and audio.available
    assert audio.uses_system_mixer


def test_audio_detects_pactl_when_no_wireplumber():
    audio = AudioService(platform="linux", which=lambda name: "/usr/bin/pactl" if name == "pactl" else None)
    assert audio.backend == "pactl" and audio.available


def test_audio_without_tools_is_unavailable_and_says_so():
    audio = AudioService(platform="linux", which=lambda _name: None)
    assert audio.backend == "none" and not audio.available
    assert "Volume unavailable" in audio.change("up")
    assert "install" in audio.detail


def test_audio_falls_back_to_multimedia_keys_on_x11():
    pressed: list[str] = []
    audio = AudioService(platform="linux", which=lambda _name: None, press_key=pressed.append)
    assert audio.backend == "media-keys"
    audio.change("up")
    audio.change("down")
    audio.toggle_mute()
    assert pressed == ["volumeup", "volumedown", "volumemute"]


def test_audio_windows_uses_native_keys():
    pressed: list[str] = []
    audio = AudioService(platform="win32", press_key=pressed.append)
    assert audio.backend == "windows-media-keys" and audio.available
    audio.change("up")
    assert pressed == ["volumeup"]
    status = audio.status()
    assert status.available and status.volume_percent is None


def test_wpctl_commands_and_status_parsing():
    calls: list[list[str]] = []

    def runner(argv):
        calls.append(list(argv))
        if argv[1] == "get-volume":
            return completed("Volume: 0.45\n")
        return completed()

    audio = AudioService(platform="linux", which=lambda n: "wpctl" if n == "wpctl" else None,
                         runner=runner)
    assert audio.change("up") == "Volume 45%"
    assert audio.toggle_mute() == "Unmuted"
    assert calls[0][:4] == ["wpctl", "set-volume", "-l", "1.5"]
    assert calls[0][-1] == "5%+"
    # status() reads the volume between actions, so match rather than index.
    assert ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"] in calls


def test_pactl_commands_and_status_parsing():
    calls: list[list[str]] = []

    def runner(argv):
        calls.append(list(argv))
        if argv[1] == "get-sink-volume":
            return completed("Volume: front-left: 32768 /  75% / -7.5 dB\n")
        if argv[1] == "get-sink-mute":
            return completed("Mute: yes\n")
        return completed()

    audio = AudioService(platform="linux", which=lambda n: "pactl" if n == "pactl" else None,
                         runner=runner)
    status = audio.status()
    assert (status.volume_percent, status.muted) == (75, True)
    audio.change("down")
    assert ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"] in calls


def test_audio_backend_failure_is_not_silently_successful():
    audio = AudioService(platform="linux", which=lambda n: "wpctl" if n == "wpctl" else None,
                         runner=lambda argv: completed(returncode=1, stderr="no such sink"))
    assert "failed" in audio.change("up")
    assert audio.status().available is False


def test_parse_helpers():
    from gestura.services.audio_service import (
        _parse_pactl_mute,
        _parse_pactl_volume,
        _parse_wpctl,
    )

    assert _parse_wpctl("Volume: 1.00 [MUTED]") == (100, True)
    assert _parse_wpctl("garbage") == (None, False)
    assert _parse_pactl_volume("Volume: mono: 100% [100%]") == 100
    assert _parse_pactl_mute("Mute: no") is False


# --------------------------------------------------------------------------- input backends
def test_input_capabilities_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    caps = detect_input_capabilities("windows")
    assert caps.available and caps.pointer and caps.keyboard and caps.scroll
    assert "SendInput" in caps.name


def test_input_capabilities_x11_requires_libxtst(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("ctypes.util.find_library", lambda name: None)
    caps = detect_input_capabilities("x11")
    assert caps.available is False and "libxtst6" in caps.detail


def test_input_capabilities_wayland_without_ydotool_is_explicit(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("shutil.which", lambda _name: None)
    caps = detect_input_capabilities("wayland")
    assert caps.available is False and caps.experimental is False
    assert "Wayland" in caps.detail


def test_select_backend_refuses_to_fake_wayland_input(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("AIRDESK_INPUT_BACKEND", raising=False)
    monkeypatch.setattr("gestura.controllers.backends.detect_input_capabilities",
                        lambda session=None: detect_input_capabilities("wayland"))
    backend, error = select_backend()
    assert backend is None
    assert "Wayland" in error and "AIRDESK_INPUT_BACKEND" in error


def test_ydotool_backend_emits_expected_commands(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr("gestura.controllers.backends.shutil.which", lambda _n: "/usr/bin/ydotool")
    backend = YdotoolBackend(runner=lambda argv: calls.append(list(argv)) or 0,
                             screen_size=(1280, 720))
    backend.move_to(10, 20)
    backend.click("left")
    backend.mouse_down("right")
    backend.mouse_up("right")
    backend.press("enter")
    backend.hotkey("ctrl", "s")
    backend.write_text("hello")
    backend.scroll(2)
    backend.hscroll(-1)
    assert calls[0] == ["ydotool", "mousemove", "--absolute", "10", "20"]
    assert calls[1] == ["ydotool", "click", "0xC0"]
    assert calls[2] == ["ydotool", "mousedown", "0xC1"]
    assert calls[3] == ["ydotool", "mouseup", "0xC1"]
    assert calls[4] == ["ydotool", "key", "enter"]
    assert calls[5] == ["ydotool", "key", "leftctrl+s"]
    assert calls[6] == ["ydotool", "type", "hello"]
    assert [c[-1] for c in calls[7:9]] == ["0x04", "0x04"]
    assert calls[9][-1] == "0x06"
    assert backend.screen_size() == (1280, 720)


# --------------------------------------------------------------------------- controllers
def test_mouse_and_keyboard_dispatch_and_release():
    be = RecordingBackend()
    mouse = MouseController(be, CursorSettings())
    keyboard = KeyboardController(be)
    mouse.move_normalized(0.5, 0.5)
    mouse.drag_start()
    keyboard.hold("ctrl")
    keyboard.press("enter")
    assert ("mouse_down", "left") in be.calls and ("press", "enter") in be.calls
    # emergency release: nothing may stay held
    mouse.release_buttons()
    keyboard.release_all()
    assert ("mouse_up", "left") in be.calls and ("key_up", "ctrl") in be.calls
    assert keyboard.held == frozenset()


def test_air_actions_route_volume_through_audio_service():
    class FakeAudio:
        def __init__(self):
            self.calls = []

        def change(self, direction):
            self.calls.append(direction)
            return f"Volume {direction}"

        def toggle_mute(self):
            self.calls.append("mute")
            return "Muted"

    be = RecordingBackend()
    audio = FakeAudio()
    runner = AirActionRunner(keyboard=KeyboardController(be), mouse=MouseController(be, CursorSettings()),
                             switch_mode=lambda name: name, toggle_keyboard=lambda: None,
                             toggle_pause=lambda: None, screenshot=lambda: "shot",
                             is_test_mode=lambda: False, audio=audio)
    assert runner.run_command("media.volume_up") == "Volume up"
    runner.run_command("media.volume_down")
    assert audio.calls == ["up", "down"]
    assert be.named("press") == [], "audio backend must replace the blind keysym path"


def test_full_report_is_serialisable_and_marks_camera_unprobed():
    import json

    report = diag.collect_full_report(probe_camera=False)
    payload = json.loads(diag.format_full_report(report, as_json=True))
    assert payload["version"] and payload["python"] and payload["input"]["backend"]
    assert payload["camera"] == []
    text = diag.format_full_report(report)
    assert "AIRDESK full diagnostics" in text and "emergency stop" in text
    assert "not probed" in text
