# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Command-line entry point: `gestura`, `python -m gestura` or `python main.py`."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("gestura")


def _camera_index(source: str | None) -> int:
    """Camera index for diagnostics: the --source index, else the configured one."""
    if source and source.isdigit():
        return int(source)
    try:
        from ..services.configuration_service import ConfigurationService

        return int(ConfigurationService().load().camera.index)
    except Exception:  # noqa: BLE001 - a bad config must not break diagnostics
        return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    from .. import APP_NAME, APP_TAGLINE

    p = argparse.ArgumentParser(
        prog=APP_NAME.lower(),
        description=f"{APP_NAME} — {APP_TAGLINE}",
    )
    p.add_argument("--diagnostics", action="store_true",
                   help="print platform / session capabilities (X11, Wayland, input) and exit")
    p.add_argument("--diagnostics-json", action="store_true",
                   help="same as --diagnostics, as JSON")
    p.add_argument("--full-diagnostics", action="store_true",
                   help="consolidated report: versions, models, input, audio, displays, camera")
    p.add_argument("--camera-diagnostics", action="store_true",
                   help="open the camera briefly and report the measured resolution and FPS")
    p.add_argument("--probe-camera", action="store_true",
                   help="with --full-diagnostics: also probe the camera for ~2 s")
    p.add_argument("--json", action="store_true",
                   help="with --full-diagnostics / --camera-diagnostics: JSON output")
    p.add_argument("--source", help="camera index, video file, image file or image folder "
                                    "(default: camera from settings)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--test-mode", dest="test_mode", action="store_true", default=None,
                      help="start in test mode (gestures shown, never executed)")
    mode.add_argument("--live", dest="test_mode", action="store_false",
                      help="start with real control enabled")
    p.add_argument("--start", action="store_true", help="start tracking immediately")
    p.add_argument("--minimized", action="store_true", help="start minimized (used by launch at login)")
    p.add_argument("--page", choices=["dashboard", "studio", "keyboard", "settings"], help="page to open")
    p.add_argument("--config-dir", help="use this folder for settings and logs")
    p.add_argument("--smoke-test", type=float, metavar="SECONDS",
                   help="start tracking, run for SECONDS, print stats as JSON and exit")
    p.add_argument("--screenshot", metavar="PNG", help="with --smoke-test: save a window screenshot")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.config_dir:
        os.environ["GESTURA_CONFIG_DIR"] = args.config_dir

    if args.diagnostics or args.diagnostics_json:
        from ..services.platform_diagnostics import format_report

        print(format_report(as_json=args.diagnostics_json or args.json))
        return 0

    if args.camera_diagnostics:
        from ..vision.camera_diagnostics import collect_camera_report, format_camera_report

        report = collect_camera_report(index=_camera_index(args.source))
        print(format_camera_report(report, as_json=args.json or args.diagnostics_json))
        return 0 if report.working_cameras else 1

    if args.full_diagnostics:
        from ..services.platform_diagnostics import format_full_report

        print(format_full_report(as_json=args.json or args.diagnostics_json,
                                 probe_camera=args.probe_camera))
        return 0

    from .bootstrap import create_qt_app, setup_logging

    setup_logging(args.verbose)
    qt = create_qt_app(sys.argv[:1])

    from ..services.configuration_service import ConfigurationService
    from .application import GesturaApp
    from .windows import build_main_window

    test_mode = True if args.smoke_test and args.test_mode is None else args.test_mode
    app = GesturaApp(ConfigurationService(), source_spec=args.source, force_test_mode=test_mode)
    window = build_main_window(app)
    if args.page:
        window.show_page(args.page)
    if (args.minimized or app.settings.startup.start_minimized) and not args.smoke_test:
        window.showMinimized()
    else:
        window.show()
    if window.keyboard_window.isVisible():
        window.keyboard_window.raise_()

    if args.start or args.smoke_test or app.settings.startup.auto_start_tracking:
        app.start()

    if args.smoke_test:
        from PySide6.QtCore import QTimer

        stats: dict = {}
        app.tracking.telemetry.connect(lambda t: stats.update(
            fps=round(t.fps, 1), latency_ms=round(t.latency_ms, 1), hand_ms=round(t.hand_ms, 1),
            face_ms=round(t.face_ms, 1), hands=t.hands_visible, face=t.face_visible,
            pose=t.hand.pose.value, head=None if not t.head.visible else
            [round(t.head.yaw, 1), round(t.head.pitch, 1), round(t.head.roll, 1)]))
        gestures: list[str] = []
        app.tracking.gesture.connect(lambda e: gestures.append(e.label))
        status: list[str] = []
        app.tracking.camera_status.connect(lambda s, m: status.append(f"{s}: {m}"))

        def finish() -> None:
            if args.screenshot:
                shot = Path(args.screenshot)
                shot.parent.mkdir(parents=True, exist_ok=True)
                window.grab().save(str(shot))
                screen = qt.primaryScreen().grabWindow(0)  # whole desktop: keyboard, overlay
                screen.save(str(shot.with_name(shot.stem + "_screen" + shot.suffix)))
            frames = app.tracking.worker.frames_processed if app.tracking.worker else 0
            print(json.dumps({"frames": frames, "last": stats, "gestures": gestures[-20:],
                              "status": status, "backend_error": app.backend_error}, indent=1))
            window.close()
            qt.exit(0 if frames > 0 else 1)

        QTimer.singleShot(int(args.smoke_test * 1000), finish)

    return qt.exec()


if __name__ == "__main__":
    sys.exit(main())
