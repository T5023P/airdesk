# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Platform / session diagnostics — especially X11 vs Wayland on Linux.

AIRDESK must never *pretend* a capability exists. This module probes what the
current session can actually do and prints it, so a Kali user can see at a glance
whether synthetic input, the emergency hotkey or the audio backend will work
before trusting a gesture.

Two entry points:

* :func:`collect_report` / :func:`format_report` — the original input/session
  probe (``airdesk --diagnostics``).
* :func:`collect_full_report` / :func:`format_full_report` — the consolidated
  report (``airdesk --full-diagnostics``): versions, camera, models, input,
  audio, displays and emergency stop, with optional JSON.

Nothing here reads personal data: no file contents, no usernames beyond what the
OS exposes in a path, no camera frames are saved.
"""

from __future__ import annotations

import ctypes.util
import json
import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class PlatformReport:
    platform: str
    session: str  # "windows" | "x11" | "wayland" | "unknown"
    display_server: str
    python: str
    input_backend: str = ""
    capabilities: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


def detect_session() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session in ("wayland", "x11"):
        return session
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def desktop_environment() -> str:
    """``XDG_CURRENT_DESKTOP`` / ``DESKTOP_SESSION`` — which desktop is running."""
    return (os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION")
            or os.environ.get("GDMSESSION") or ("Windows" if sys.platform == "win32" else "unknown"))


def collect_report() -> PlatformReport:
    session = detect_session()
    report = PlatformReport(
        platform=platform.platform(),
        session=session,
        display_server=os.environ.get("XDG_SESSION_TYPE") or os.environ.get("DISPLAY")
        or os.environ.get("WAYLAND_DISPLAY") or "n/a",
        python=platform.python_version(),
    )

    try:
        import pyautogui  # noqa: F401

        report.capabilities["synthetic_input"] = True
        report.input_backend = "PyAutoGUI (Win32 SendInput / XTest)"
        try:
            w, h = pyautogui.size()
            report.capabilities["screen_query"] = bool(w and h)
            report.notes.append(f"screen: {w}x{h}")
        except Exception as exc:  # noqa: BLE001
            report.capabilities["screen_query"] = False
            report.unsupported.append(f"Screen size query failed: {exc}")
    except Exception as exc:  # noqa: BLE001 - no display, missing tkinter, etc.
        report.capabilities["synthetic_input"] = False
        report.unsupported.append(f"PyAutoGUI unavailable: {exc}")

    if sys.platform == "win32":
        report.capabilities["win32_sendinput"] = True
    elif session == "x11":
        report.capabilities["xtest"] = bool(ctypes.util.find_library("Xtst"))
        report.capabilities["x11_backend"] = True
        if not report.capabilities["xtest"]:
            report.unsupported.append("libXtst is missing: install libxtst6 for X11 input.")
    else:
        report.capabilities["xtest"] = False
        report.capabilities["x11_backend"] = False
        if session == "wayland":
            report.notes.append(
                "Wayland blocks synthetic input for normal apps. Use an X11 session "
                "(recommended on Kali) or run ydotool as a user service."
            )

    if sys.platform.startswith("linux"):
        report.capabilities["uinput"] = os.path.exists("/dev/uinput") and os.access(
            "/dev/uinput", os.W_OK
        )
        report.capabilities["ydotool"] = bool(shutil.which("ydotool"))
        report.capabilities["global_hotkey"] = False
        report.unsupported.append(
            "System-wide emergency hotkey is Windows-only; use the physical mouse corner "
            "fail-safe or the in-app Ctrl+Shift+G shortcut on Linux."
        )
        report.capabilities["multimedia_keys"] = True
        report.notes.append("Multimedia keys are sent through PyAutoGUI (best effort).")
    else:
        report.capabilities["global_hotkey"] = True
        report.capabilities["uinput"] = False
        report.capabilities["ydotool"] = False
        report.capabilities["multimedia_keys"] = True

    if not report.capabilities.get("synthetic_input") and sys.platform.startswith("linux"):
        report.unsupported.append(
            "No synthetic input: install python3-tk (for PyAutoGUI) and check DISPLAY; "
            "the dashboard will run in simulation only."
        )
    return report


def format_report(report: PlatformReport | None = None, as_json: bool = False) -> str:
    report = report or collect_report()
    if as_json:
        return json.dumps(asdict(report), indent=2)
    lines = [
        "AIRDESK platform diagnostics",
        f"  platform     {report.platform}",
        f"  python       {report.python}",
        f"  session      {report.session}  ({report.display_server})",
        f"  input        {report.input_backend or 'simulation only'}",
        "  capabilities:",
    ]
    for name, ok in sorted(report.capabilities.items()):
        lines.append(f"    {'OK  ' if ok else 'NO  '} {name}")
    if report.notes:
        lines.append("  notes:")
        lines.extend(f"    - {note}" for note in report.notes)
    if report.unsupported:
        lines.append("  unsupported / degraded:")
        lines.extend(f"    - {item}" for item in report.unsupported)
    return "\n".join(lines)


# --------------------------------------------------------------------------- full report
@dataclass(slots=True)
class FullReport:
    """Everything a support request or a deployment check needs, in one object."""

    app: str = "AIRDESK"
    version: str = ""
    upstream: str = ""
    python: str = ""
    implementation: str = ""
    os: str = ""
    architecture: str = ""
    session: str = ""
    desktop: str = ""
    display_server: str = ""
    packages: dict[str, str] = field(default_factory=dict)
    models: list[dict[str, Any]] = field(default_factory=list)
    camera: list[dict[str, Any]] = field(default_factory=list)
    input: dict[str, Any] = field(default_factory=dict)
    audio: dict[str, Any] = field(default_factory=dict)
    displays: list[dict[str, Any]] = field(default_factory=list)
    emergency_stop: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    unsupported: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when the essentials for a real session are present."""
        return bool(self.input.get("available")) and bool(self.audio.get("backend"))


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for module, label in (("cv2", "opencv"), ("mediapipe", "mediapipe"),
                          ("PySide6", "pyside6"), ("pyautogui", "pyautogui"),
                          ("numpy", "numpy"), ("pydantic", "pydantic")):
        try:
            mod = __import__(module)
            versions[label] = str(getattr(mod, "__version__", "installed"))
        except Exception as exc:  # noqa: BLE001 - report the import failure text
            versions[label] = f"MISSING ({type(exc).__name__})"
    return versions


def collect_full_report(*, probe_camera: bool = False, camera_seconds: float = 2.0,
                        max_camera_index: int = 3) -> FullReport:
    import gestura

    report = FullReport(
        version=gestura.__version__,
        upstream=gestura.UPSTREAM_URL,
        python=platform.python_version(),
        implementation=platform.python_implementation(),
        os=platform.platform(),
        architecture=platform.machine(),
        session=detect_session(),
        desktop=desktop_environment(),
        display_server=(os.environ.get("WAYLAND_DISPLAY") and f"wayland:{os.environ['WAYLAND_DISPLAY']}")
        or os.environ.get("DISPLAY") or ("windows" if sys.platform == "win32" else "n/a"),
    )
    report.packages = _package_versions()

    from ..vision.models import verify_models

    for check in verify_models():
        report.models.append({
            "name": check.name,
            "present": check.present,
            "size_bytes": check.size,
            "checksum_ok": check.hash_ok,
            "path": str(check.path),
            "detail": check.detail,
        })
        if not check.present:
            report.unsupported.append(f"Model missing: {check.name} ({check.detail})")
        elif check.hash_ok is False:
            report.unsupported.append(f"Model checksum mismatch: {check.name}")

    from ..controllers.backends import detect_input_capabilities

    caps = detect_input_capabilities(report.session)
    report.input = {
        "session": caps.session,
        "backend": caps.name,
        "available": caps.available,
        "experimental": caps.experimental,
        "pointer": caps.pointer,
        "keyboard": caps.keyboard,
        "scroll": caps.scroll,
        "detail": caps.detail,
    }
    if not caps.available:
        report.unsupported.append(f"Input: {caps.detail}")

    from .audio_service import AudioService

    audio = AudioService().status()
    report.audio = {
        "backend": audio.backend,
        "available": audio.available,
        "volume_percent": audio.volume_percent,
        "muted": audio.muted,
        "detail": audio.detail or audio.summary(),
    }
    if not audio.available:
        report.unsupported.append(f"Audio: {audio.detail or audio.summary()}")
    elif audio.volume_percent is None:
        report.notes.append(f"Audio level readout unavailable ({audio.backend}).")

    try:
        for display in _probe_displays():
            report.displays.append({
                "index": display.index, "name": display.name,
                "x": display.x, "y": display.y,
                "width": display.width, "height": display.height,
                "primary": display.primary,
            })
    except Exception as exc:  # noqa: BLE001 - headless
        report.notes.append(f"Display enumeration unavailable: {exc}")

    report.emergency_stop = {
        "in_app_shortcut": "Ctrl+Shift+G (works everywhere)",
        "global_hotkey": sys.platform == "win32",
        "physical_mouse_corner": sys.platform == "win32",
        "open_palm_gesture": True,
    }
    if sys.platform != "win32":
        report.unsupported.append(
            "Global Ctrl+Alt+Shift+G hotkey is Windows-only; the in-app shortcut, the "
            "EMERGENCY STOP button and the open-palm gesture remain available on Linux."
        )

    from .configuration_service import config_dir

    report.config = {
        "directory": str(config_dir()),
        "exists": config_dir().is_dir(),
        "settings_file": str(config_dir() / "settings.json"),
    }

    if probe_camera:
        from ..vision.camera_diagnostics import collect_camera_report

        probe = collect_camera_report(index=_selected_camera_index(), seconds=camera_seconds,
                                     max_index=max_camera_index)
        report.camera = [asdict(p) | {"working": p.working} for p in probe.probes]
        report.notes.extend(probe.notes)
        if not probe.working_cameras:
            report.unsupported.append("Camera: no camera delivered frames during the probe.")
    else:
        report.notes.append("Camera not probed (add --probe-camera to open it for ~2 s).")
    return report


def _probe_displays() -> list:
    """Enumerate displays from a CLI process (Qt needs an instance to answer).

    A ``QApplication`` is created rather than a bare ``QGuiApplication``: Qt
    allows exactly one application object per process, and the GUI tests need a
    widget-capable one. Reusing the same class keeps both paths working.
    """
    from .display_service import enumerate_displays

    try:
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is None:
            QApplication([])
    except Exception:  # noqa: BLE001 - headless / no Qt platform plugin
        return []
    return enumerate_displays()


def _selected_camera_index() -> int:
    """Best effort: the configured camera index, defaulting to 0."""
    try:
        from .configuration_service import ConfigurationService

        return int(ConfigurationService().load().camera.index)
    except Exception:  # noqa: BLE001 - diagnostics must not fail on a bad config
        return 0


def format_full_report(report: FullReport | None = None, as_json: bool = False,
                       *, probe_camera: bool = False) -> str:
    report = report or collect_full_report(probe_camera=probe_camera)
    if as_json:
        return json.dumps(asdict(report), indent=2)

    lines = [
        f"{report.app} full diagnostics",
        f"  version      {report.version}  (derived from {report.upstream})",
        f"  python       {report.python} {report.implementation}",
        f"  os           {report.os}",
        f"  arch         {report.architecture}",
        f"  session      {report.session}  desktop={report.desktop}  display={report.display_server}",
        "  packages:",
    ]
    for name, version in sorted(report.packages.items()):
        lines.append(f"    {name:<10} {version}")
    lines.append("  models:")
    for model in report.models:
        if model["present"]:
            state = "ok" if model["checksum_ok"] else ("unverified" if model["checksum_ok"] is None
                                                       else "CHECKSUM MISMATCH")
            lines.append(f"    {model['name']:<22} {model['size_bytes'] / 1_048_576:.1f} MiB  {state}")
        else:
            lines.append(f"    {model['name']:<22} MISSING  ({model['detail']})")
    lines.append("  input:")
    lines.append(f"    backend      {report.input.get('backend')}")
    for key in ("available", "experimental", "pointer", "keyboard", "scroll"):
        lines.append(f"    {key:<12} {report.input.get(key)}")
    if report.input.get("detail"):
        lines.append(f"    detail       {report.input['detail']}")
    lines.append("  audio:")
    lines.append(f"    backend      {report.audio.get('backend')}")
    lines.append(f"    available    {report.audio.get('available')}")
    if report.audio.get("volume_percent") is not None:
        lines.append(f"    volume       {report.audio['volume_percent']}%")
    if report.audio.get("muted") is not None:
        lines.append(f"    muted        {report.audio['muted']}")
    if report.audio.get("detail"):
        lines.append(f"    detail       {report.audio['detail']}")
    lines.append("  displays:")
    if report.displays:
        for display in report.displays:
            tag = " (primary)" if display["primary"] else ""
            lines.append(f"    {display['index']}: {display['name']} "
                         f"{display['width']}x{display['height']} at "
                         f"({display['x']},{display['y']}){tag}")
    else:
        lines.append("    none detected (no Qt screen available)")
    lines.append("  camera:")
    if report.camera:
        for camera in report.camera:
            if camera["working"]:
                lines.append(f"    camera {camera['index']}: {camera['width']}x{camera['height']} "
                             f"@ {camera['measured_fps']:.1f} FPS")
            else:
                lines.append(f"    camera {camera['index']}: FAILED — {camera['error']}")
    else:
        lines.append("    not probed")
    lines.append("  emergency stop:")
    for key, value in report.emergency_stop.items():
        lines.append(f"    {key:<22} {value}")
    lines.append(f"  config       {report.config.get('directory')} "
                 f"({'present' if report.config.get('exists') else 'created on first run'})")
    if report.notes:
        lines.append("  notes:")
        lines.extend(f"    - {note}" for note in report.notes)
    if report.unsupported:
        lines.append("  unsupported / degraded:")
        lines.extend(f"    - {item}" for item in report.unsupported)
    else:
        lines.append("  unsupported / degraded: none detected")
    return "\n".join(lines)


def write_full_report(path: Path, *, probe_camera: bool = False) -> Path:
    """Save the JSON report next to a log file for support (no personal data)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_full_report(as_json=True, probe_camera=probe_camera), encoding="utf-8")
    return path
