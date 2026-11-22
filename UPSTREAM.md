# Upstream attribution — AIRDESK is derived from Gestura

AIRDESK is a derivative work of the open-source **Gestura** project. It is not a
clean-room rewrite, and this document exists so that the origin of the code is
unambiguous for users, distributors and future maintainers.

| | |
|---|---|
| **Upstream project** | Gestura — hands-free desktop control with a webcam |
| **Upstream author** | Raphzaf and the Gestura contributors |
| **Upstream repository** | <https://github.com/Raphzaf/gestura> |
| **Upstream versions used** | v0.1.0 – v0.3.0 (`main` at the time of the fork) |
| **Licence** | GNU General Public License v3.0 or later (`LICENSE`) |
| **Derivative** | AIRDESK v0.4.0, same licence, distributed under the same terms |

## What was inherited

The following modules are upstream work, kept and (where noted) extended rather
than replaced:

* `gestura/vision/` — webcam capture, MediaPipe hand/face landmark detection, feature
  extraction and smoothing.
* `gestura/gestures/` — pose classification, gesture state machine, debouncing.
* `gestura/core/` — command registry and allow-list, command engine, safety manager.
* `gestura/controllers/` — mouse/keyboard controllers, Windows and X11 backends.
* `gestura/services/` — tracking worker/service, configuration service, hotkeys.
* `gestura/ui/` — PySide6 application shell, dashboard, Gesture Studio, settings,
  calibration wizard, virtual keyboard, feedback overlay, shared widgets.
* `gestura/app/` — entry point, bootstrap, window wiring, mode handling.
* `tests/` — the entire upstream test suite, still running unmodified.
* `docs/` — architecture, gesture reference, privacy and packaging documentation.
* Packaging: `pyproject.toml`, `gestura.spec`, `installer/`, `store/`, `scripts/`.

## What AIRDESK added

New files (all carrying the upstream SPDX header and GPL notice):

* `gestura/core/air_commands.py` — the fixed Air Command allow-list.
* `gestura/core/command_wheel.py` — pure radial-selection state machine.
* `gestura/gestures/chords.py` — configurable two-hand chords.
* `gestura/macros/` — macro model, atomic JSON store and sequential runner.
* `gestura/controllers/air_actions.py` — allow-listed desktop actions (launch, capture).
* `gestura/services/display_service.py` — display enumeration and coordinate mapping.
* `gestura/services/platform_diagnostics.py` — X11/Wayland capability reporting.
* `gestura/ui/air_command/` — the click-through radial wheel overlay.
* `gestura/ui/macros/` — the visual macro editor page.
* `website/` — this project's website (AIRDESK-specific, not upstream).
* Tests for each of the above (`tests/test_air_commands.py`, `test_command_wheel.py`,
  `test_chords.py`, `test_macros.py`, `test_displays.py`).

Existing files were modified in place to wire these features (settings model,
tracking worker, application, dashboard, main window, theme, settings page,
bootstrap, command registry, mouse controller). No upstream module was deleted and
no working implementation was replaced.

## Licence obligations

Gestura and AIRDESK are both licensed **GPL-3.0-or-later**. If you distribute
AIRDESK, or a modified version of it, you must:

1. keep the `LICENSE` file and the copyright notices intact;
2. keep this attribution and the upstream project reference;
3. provide the corresponding source code under the same licence;
4. state changes if you modify the work further.

The full licence text is in [`LICENSE`](LICENSE). Copyright in the inherited code
remains with the Gestura contributors; copyright in the AIRDESK additions is held
by the AIRDESK contributors and licensed under the same terms.

## Not affiliated

AIRDESK is an independent derivative. It is not endorsed by, sponsored by, or
affiliated with the upstream author beyond the obligations of the GPL.
