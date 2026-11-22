# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Volume control that adapts to the platform it is actually running on.

Windows has no single command-line mixer, so AIRDESK keeps using the multimedia
key path (``VK_VOLUME_UP`` …) that the rest of the Windows build already relies
on. Linux does **not** have media keys in the same sense: the correct local tool
depends on the sound server, so we detect it instead of assuming:

* **PipeWire / WirePlumber** → ``wpctl``
* **PulseAudio-compatible**  → ``pactl``
* otherwise                  → the multimedia-key fallback, reported as such

Everything is local, uses fixed argv lists (``shell=False``) and never requires
root. When no backend is usable, :meth:`AudioService.change` returns a clear
message instead of pretending the volume changed.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Sequence

log = logging.getLogger(__name__)

#: Percent per step, matching the feel of one multimedia-key press.
STEP_PERCENT = 5
#: Never let gesture spam push the sink into clipping.
MAX_VOLUME_PERCENT = 150

_WPCTL = "wpctl"
_PACTL = "pactl"


@dataclass(slots=True)
class AudioStatus:
    """What the audio layer can do right now (used by diagnostics)."""

    backend: str
    available: bool
    volume_percent: int | None = None
    muted: bool | None = None
    detail: str = ""

    def summary(self) -> str:
        if not self.available:
            return f"{self.backend}: unavailable ({self.detail})" if self.detail else \
                f"{self.backend}: unavailable"
        bits = [self.backend]
        if self.volume_percent is not None:
            bits.append(f"{self.volume_percent}%")
        if self.muted is not None:
            bits.append("muted" if self.muted else "unmuted")
        return " · ".join(bits)


def _default_run(argv: Sequence[str]) -> subprocess.CompletedProcess | None:
    """Run a fixed argv list; return None when the tool is missing or fails."""
    try:
        return subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            list(argv),
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - host specific
        log.debug("audio command failed: %s (%s)", argv[0], exc)
        return None


class AudioService:
    """Volume up / down / mute with runtime backend detection."""

    def __init__(
        self,
        *,
        platform: str | None = None,
        which: Callable[[str], str | None] = shutil.which,
        runner: Callable[[Sequence[str]], subprocess.CompletedProcess | None] | None = None,
        press_key: Callable[[str], None] | None = None,
    ) -> None:
        self.platform = platform or sys.platform
        self._which = which
        self._run = runner or _default_run
        self._press_key = press_key
        self._tested = False
        self.backend, self.detail = self._detect()

    # ------------------------------------------------------------- detection
    def _detect(self) -> tuple[str, str]:
        if self.platform == "win32":
            return "windows-media-keys", "Win32 multimedia keys (VK_VOLUME_*)"
        if self.platform == "darwin":
            return "unsupported", "macOS is not a supported AIRDESK target"
        has_wpctl = bool(self._which(_WPCTL))
        has_pactl = bool(self._which(_PACTL))
        if has_wpctl:
            return "wpctl", "PipeWire / WirePlumber"
        if has_pactl:
            return "pactl", "PulseAudio-compatible"
        if self._press_key is not None:
            return "media-keys", "no wpctl/pactl found; falling back to X11 multimedia keys"
        return "none", "install wireplumber (wpctl) or pulseaudio-utils (pactl)"

    @property
    def available(self) -> bool:
        if self.backend in ("wpctl", "pactl", "windows-media-keys"):
            # On Windows the multimedia-key path is native; the audio level is
            # simply not readable through it (reported separately).
            return True
        if self.backend == "media-keys":
            return self._press_key is not None
        return False

    @property
    def uses_system_mixer(self) -> bool:
        return self.backend in ("wpctl", "pactl")

    # ------------------------------------------------------------- internals
    def _sink(self) -> str:
        return "@DEFAULT_AUDIO_SINK@" if self.backend == "wpctl" else "@DEFAULT_SINK@"

    def _exec(self, argv: Sequence[str]) -> subprocess.CompletedProcess | None:
        if not self.available or not self.uses_system_mixer:
            return None
        return self._run(argv)

    def _ok(self, proc: subprocess.CompletedProcess | None) -> bool:
        return proc is not None and proc.returncode == 0

    def _media_key(self, key: str) -> bool:
        if self._press_key is None:
            return False
        try:
            self._press_key(key)
            return True
        except Exception:  # noqa: BLE001 - backend may be simulation-only
            log.debug("multimedia key %s failed", key, exc_info=True)
            return False

    # --------------------------------------------------------------- actions
    def change(self, direction: str) -> str:
        """Raise or lower the volume. Returns a message for the UI overlay."""
        step = f"{STEP_PERCENT}%+"
        if direction == "down":
            step = f"{STEP_PERCENT}%-"
        if self.backend == "wpctl":
            proc = self._exec([
                _WPCTL, "set-volume", "-l", str(MAX_VOLUME_PERCENT / 100),
                self._sink(), step,
            ])
            if self._ok(proc):
                status = self.status()
                return f"Volume {status.volume_percent}%" if status.volume_percent is not None \
                    else "Volume changed"
            return f"wpctl failed: {self._stderr(proc)}"
        if self.backend == "pactl":
            proc = self._exec([_PACTL, "set-sink-volume", self._sink(), f"+{STEP_PERCENT}%"
                               if direction == "up" else f"-{STEP_PERCENT}%"])
            if self._ok(proc):
                status = self.status()
                return f"Volume {status.volume_percent}%" if status.volume_percent is not None \
                    else "Volume changed"
            return f"pactl failed: {self._stderr(proc)}"
        if self.backend in ("windows-media-keys", "media-keys"):
            key = "volumeup" if direction == "up" else "volumedown"
            return f"Volume {'up' if direction == 'up' else 'down'}" if self._media_key(key) \
                else "Volume unavailable: no multimedia-key backend"
        return f"Volume unavailable: {self.detail}"

    def set_muted(self, muted: bool) -> str:
        if self.backend == "wpctl":
            proc = self._exec([_WPCTL, "set-mute", self._sink(), "1" if muted else "0"])
            return ("Muted" if muted else "Unmuted") if self._ok(proc) \
                else f"wpctl failed: {self._stderr(proc)}"
        if self.backend == "pactl":
            proc = self._exec([_PACTL, "set-sink-mute", self._sink(), "1" if muted else "0"])
            return ("Muted" if muted else "Unmuted") if self._ok(proc) \
                else f"pactl failed: {self._stderr(proc)}"
        if self.backend in ("windows-media-keys", "media-keys"):
            key = "volumemute"
            return "Toggled mute" if self._media_key(key) else "Mute unavailable"
        return f"Mute unavailable: {self.detail}"

    def toggle_mute(self) -> str:
        """Toggle the sink mute state (preferred over blind set_mute)."""
        if self.backend == "wpctl":
            proc = self._exec([_WPCTL, "set-mute", self._sink(), "toggle"])
            if self._ok(proc):
                status = self.status()
                return "Muted" if status.muted else "Unmuted"
            return f"wpctl failed: {self._stderr(proc)}"
        if self.backend == "pactl":
            proc = self._exec([_PACTL, "set-sink-mute", self._sink(), "toggle"])
            if self._ok(proc):
                status = self.status()
                return "Muted" if status.muted else "Unmuted"
            return f"pactl failed: {self._stderr(proc)}"
        if self.backend in ("windows-media-keys", "media-keys"):
            return "Toggled mute" if self._media_key("volumemute") else "Mute unavailable"
        return f"Mute unavailable: {self.detail}"

    # ---------------------------------------------------------------- status
    def status(self) -> AudioStatus:
        if self.backend == "wpctl":
            proc = self._exec([_WPCTL, "get-volume", self._sink()])
            if not self._ok(proc):
                return AudioStatus(self.backend, False, detail=self._stderr(proc) or "wpctl failed")
            text = (proc.stdout or "").strip()
            volume, muted = _parse_wpctl(text)
            return AudioStatus(self.backend, True, volume, muted, text or self.detail)
        if self.backend == "pactl":
            volume_proc = self._exec([_PACTL, "get-sink-volume", self._sink()])
            mute_proc = self._exec([_PACTL, "get-sink-mute", self._sink()])
            if not self._ok(volume_proc) and not self._ok(mute_proc):
                return AudioStatus(self.backend, False,
                                   detail=self._stderr(volume_proc) or "pactl failed")
            volume = _parse_pactl_volume((volume_proc.stdout or "") if volume_proc else "")
            muted = _parse_pactl_mute((mute_proc.stdout or "") if mute_proc else "")
            return AudioStatus(self.backend, True, volume, muted, self.detail)
        if self.backend in ("windows-media-keys", "media-keys"):
            return AudioStatus(
                self.backend, self.available,
                detail="multimedia keys; volume level readout is not exposed by this API",
            )
        return AudioStatus(self.backend, False, detail=self.detail)

    def _stderr(self, proc: subprocess.CompletedProcess | None) -> str:
        if proc is None:
            return "command did not run"
        return ((proc.stderr or "").strip() or f"exit code {proc.returncode}")[:160]


def _parse_wpctl(text: str) -> tuple[int | None, bool | None]:
    """``Volume: 0.45`` / ``Volume: 0.45 [MUTED]`` → (45, True)."""
    match = re.search(r"Volume:\s*([0-9.]+)", text)
    volume = int(round(float(match.group(1)) * 100)) if match else None
    muted = "[MUTED]" in text.upper() if text else None
    return volume, muted


def _parse_pactl_volume(text: str) -> int | None:
    match = re.search(r"(\d+)%", text)
    return int(match.group(1)) if match else None


def _parse_pactl_mute(text: str) -> bool | None:
    lowered = text.lower()
    if "mute: yes" in lowered:
        return True
    if "mute: no" in lowered:
        return False
    return None
