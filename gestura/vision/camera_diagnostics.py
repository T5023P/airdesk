# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Camera diagnostics: prove a stream exists, do not infer it from a device file.

A ``/dev/video0`` node, or a camera listed by Windows, only says that a driver is
present. This module opens the device, reads real frames for a couple of seconds
and reports the measured frame rate — or the exact reason it failed.

It must only run when the application is **not** tracking: a webcam has a single
capture owner, and probing it from a second process either fails or steals frames.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

SYSFS_V4L = Path("/sys/class/video4linux")


@dataclass(slots=True)
class CameraProbe:
    index: int
    opened: bool
    width: int = 0
    height: int = 0
    frames: int = 0
    measured_fps: float = 0.0
    seconds: float = 0.0
    error: str = ""
    device: str = ""

    @property
    def working(self) -> bool:
        """A stream that delivered frames, not merely an open handle."""
        return self.opened and self.frames > 0 and self.width > 0 and self.height > 0

    def summary(self) -> str:
        if not self.opened:
            return f"camera {self.index}: NOT AVAILABLE — {self.error}"
        if self.frames == 0:
            return f"camera {self.index}: opened {self.width}x{self.height} but no frames — {self.error}"
        return (f"camera {self.index}: {self.width}x{self.height} @ {self.measured_fps:.1f} FPS "
                f"({self.frames} frames in {self.seconds:.1f}s)")


@dataclass(slots=True)
class CameraReport:
    probes: list[CameraProbe] = field(default_factory=list)
    devices: list[str] = field(default_factory=list)
    selected_index: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def working_cameras(self) -> list[CameraProbe]:
        return [p for p in self.probes if p.working]


def list_video_devices() -> list[str]:
    """Linux device nodes and their kernel names, when sysfs is available."""
    if not sys.platform.startswith("linux") or not SYSFS_V4L.is_dir():
        return []
    devices: list[str] = []
    try:
        for entry in sorted(SYSFS_V4L.iterdir()):
            name_file = entry / "name"
            try:
                label = name_file.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                label = ""
            devices.append(f"/dev/{entry.name}" + (f" — {label}" if label else ""))
    except OSError:  # pragma: no cover - unreadable sysfs
        return []
    return devices


def probe_camera(
    index: int,
    width: int = 640,
    height: int = 480,
    fps: int = 30,
    backend: str = "auto",
    *,
    seconds: float = 2.0,
    source_factory: Callable | None = None,
) -> CameraProbe:
    """Open one camera and measure the real frame rate over ``seconds``."""
    if source_factory is None:
        from .camera_manager import CameraSource

        def source_factory(**kwargs):
            return CameraSource(**kwargs)

    probe = CameraProbe(index=index, opened=False, device=f"/dev/video{index}"
                        if sys.platform.startswith("linux") else f"index {index}")
    source = source_factory(index=index, width=width, height=height, fps=fps, backend=backend)
    started = time.monotonic()
    try:
        if not source.open():
            probe.error = _open_error(index)
            return probe
        probe.opened = True
        size = getattr(source, "frame_size", None)
        if size:
            probe.width, probe.height = int(size[0]), int(size[1])
        deadline = started + max(0.2, seconds)
        first: float | None = None
        while time.monotonic() < deadline:
            frame = source.read()
            if frame is None:
                time.sleep(0.01)
                continue
            if first is None:
                first = time.monotonic()
                probe.height, probe.width = int(frame.shape[0]), int(frame.shape[1])
            probe.frames += 1
        probe.seconds = max(1e-3, time.monotonic() - (first or started))
        probe.measured_fps = probe.frames / probe.seconds if probe.frames else 0.0
        if probe.frames == 0:
            probe.error = ("the device opened but delivered no frames — it may be held by "
                           "another application or the driver rejected the requested format")
        return probe
    except Exception as exc:  # noqa: BLE001 - report, never crash diagnostics
        probe.error = f"{type(exc).__name__}: {exc}"
        return probe
    finally:
        try:
            source.release()
        except Exception:  # noqa: BLE001
            log.debug("camera release failed", exc_info=True)
        probe.seconds = probe.seconds or max(1e-3, time.monotonic() - started)


def _open_error(index: int) -> str:
    if sys.platform.startswith("linux"):
        return (f"could not open /dev/video{index} — check `v4l2-ctl --list-devices`, that no other "
                "app is using it, and that your user is in the `video` group (log out/in after adding)")
    return (f"could not open camera {index} — check that it is connected, not used by another app, "
            "and allowed in Settings > Privacy & security > Camera")


def collect_camera_report(
    *,
    index: int = 0,
    width: int = 640,
    height: int = 480,
    fps: int = 30,
    backend: str = "auto",
    max_index: int = 3,
    seconds: float = 2.0,
    probe_all: bool = False,
    source_factory: Callable | None = None,
) -> CameraReport:
    """Probe the selected camera (and optionally the other indices)."""
    report = CameraReport(devices=list_video_devices(), selected_index=index)
    indices = [index] if not probe_all else list(dict.fromkeys([index, *range(max_index)]))
    for i in indices:
        report.probes.append(probe_camera(i, width, height, fps, backend,
                                          seconds=seconds, source_factory=source_factory))
    if report.working_cameras:
        report.notes.append("A camera delivered frames. This proves capture only, not gesture accuracy.")
    else:
        report.notes.append("No camera delivered frames — see the error above before launching tracking.")
    return report


def format_camera_report(report: CameraReport | None = None, as_json: bool = False) -> str:
    report = report or collect_camera_report()
    if as_json:
        payload = {
            "selected_index": report.selected_index,
            "devices": report.devices,
            "cameras": [asdict(p) | {"working": p.working} for p in report.probes],
            "notes": report.notes,
        }
        return json.dumps(payload, indent=2)
    lines = ["AIRDESK camera diagnostics", f"  selected camera index: {report.selected_index}"]
    if report.devices:
        lines.append("  video devices:")
        lines.extend(f"    {device}" for device in report.devices)
    lines.append("  probes:")
    lines.extend(f"    {probe.summary()}" for probe in report.probes)
    if report.notes:
        lines.append("  notes:")
        lines.extend(f"    - {note}" for note in report.notes)
    return "\n".join(lines)
