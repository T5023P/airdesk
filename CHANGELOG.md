# Changelog

## Unreleased — Windows/Kali portability and deployment

No feature was removed and no module was replaced; this is the deployment layer on
top of 0.4.0.

* **Setup scripts** — `scripts/bootstrap_windows.ps1`, `scripts/run_airdesk_windows.ps1`,
  `scripts/bootstrap_kali.sh`, `scripts/run_airdesk_kali.sh` and
  `scripts/make_source_archive.sh`. Per-user virtual environment, pinned install,
  import + model verification, clear failure messages, no admin rights, no
  `sudo pip`, no `--break-system-packages`, never root.
* **Camera diagnostics** — `airdesk --camera-diagnostics` opens the device and reports
  the negotiated resolution, frames read and *measured* FPS (non-zero exit when no
  stream). A device node alone is never treated as proof.
* **Full diagnostics** — `airdesk --full-diagnostics [--json] [--probe-camera]`: version,
  Python, OS, architecture, desktop session, packages, model checksums, input backend,
  audio backend, displays, camera and emergency-stop availability. No personal data.
* **Audio** — new `services/audio_service.py`: `wpctl` (PipeWire) → `pactl` →
  multimedia-key fallback, with real path readout (`wpctl get-volume`), mute toggle and
  explicit failure messages. Windows keeps the native multimedia-key path.
* **Input backends** — session-aware `select_backend()`: PyAutoGUI on Windows/X11;
  on Wayland nothing is selected automatically (the compositor blocks XTest) and the
  reason is reported. An opt-in `ydotool` backend exists for Wayland and is marked
  experimental/unverified.
* **Models** — `verify_models()` with pinned SHA-256, non-raising checks for diagnostics,
  bundle-aware relative paths.
* **Tests** — 33 platform tests (`tests/test_platform_support.py`): 237 total,
  230 passed / 7 skipped on Windows 11.
* **Docs** — `docs/DEVELOPMENT_WINDOWS.md`, `docs/DEPLOYMENT_KALI.md`,
  `docs/PLATFORM_COMPATIBILITY.md`, `docs/TESTING_GUIDE.md`, extended
  `docs/TROUBLESHOOTING.md`.

## 0.4.0 — AIRDESK

AIRDESK is a derivative of Gestura; everything below is new on top of the 0.3.0
foundation (see `UPSTREAM.md` for the exact split).

* **Rebranding**: product identity is AIRDESK (“Your hands. Your computer. No touch
  required.”), new deep-navy glass theme, brand strings centralised in
  `gestura/__init__.py`. Window titles, sidebar, dashboard and CLI follow it. The
  Python package stays `gestura` so every existing import, test and GPL header keeps
  working, and the upstream attribution remains in the UI footer.
* **AIR COMMAND**: a 12-sector radial menu driven by a pure state machine
  (`core/command_wheel.py`). Left fist opens it after a hold, the right index selects,
  pinch confirms, open palm cancels, with a dead zone, confirm-edge detection and a
  cooldown. Every sector maps to an entry of a fixed allow-list
  (`core/air_commands.py` + `core/gesture_registry.py`); gesture input can never
  compose a shell command. Rendered by a click-through overlay and mirrored on the
  Dashboard.
* **AIR MACROS**: visual editor (`ui/macros/`) with create / edit / delete / enable /
  reorder / delay / test / save, backed by an atomic JSON store and a sequential
  runner. Steps are restricted to allow-listed apps, shortcuts, modes, volume steps,
  presentation navigation and wheel commands; destructive runs can require an
  explicit confirmation. Nothing in the model can express a shell command.
* **Two-hand chords**: configurable `left_<pose>+right_<pose>` pairs with debounce and
  cooldown, fed only while the wheel is closed so the two systems never overlap.
* **Multi-monitor control**: displays are enumerated from Qt, one is selectable, and
  normalized hand coordinates map into that display’s geometry (including negative
  origins) with DPI-aware scaling. Switching displays glides in bounded steps instead
  of teleporting the cursor; single-monitor behaviour is unchanged when no display
  provider is present.
* **Linux/Kali groundwork**: X11/Wayland detection and a capability report
  (`--diagnostics`, `--diagnostics-json`), explicit “unsupported” reporting instead of
  silent failure, and a Kali guide (`docs/LINUX_KALI.md`). No root requirement.
* **Dashboard**: Air Command card (mode badge, live selection, enable switch), active
  display selector with refresh, AIR MACROS shortcut, recording-free status cards.
* **Tests**: 61 new tests covering the wheel, the allow-list, chords, macros
  (validation, store, runner) and display/multi-monitor mapping — 204 passed,
  7 skipped on Windows 11 (237 total after the portability work below).

## Unreleased (pre-AIRDESK)

* Gestura is now licensed under the **GNU GPL v3 or later**: `LICENSE` file at the
  root, SPDX header in every source file (checked by a test and by
  `scripts/license_headers.py --check`), license shown by the installer and shipped
  with the executable. The unused GPL dependency `mouseinfo` is no longer bundled.
* **Microsoft Store build profile** (`store/`): `store/build_store.py` renders the MSIX
  manifest and logos, builds with PyInstaller into `store/out/`, packs with `makeappx`,
  optionally test-signs and submits to Partner Center (`msstore`). Identity and secrets
  come from environment variables / `store/.env` (git-ignored, values masked in logs);
  manual GitHub Actions workflow `Microsoft Store`. In the packaged app, launch at
  sign-in is a Windows startup task (Settings > Apps > Startup) instead of the Run key.

## 0.3.0

* **Two-hand mouse** (Dashboard switch): the control hand moves the cursor, scrolls,
  swipes and sets the volume; the other hand pinches to click, drag and right-click.
  The cursor no longer moves when you click. The preview colours the moving hand blue
  and the clicking hand green.

## 0.2.0

* **Drag and drop**: pinch and hold ½ s, move, release. The mouse button is always
  released if the hand is lost, on pause, stop or emergency stop.
* **Zoom**: spread / bring together two open hands (Ctrl + wheel).
* **Window management**: three-finger swipe left / right snaps the window (Win+←/→);
  maximize, minimize, show desktop and task view can be assigned to any gesture.
* **Volume**: three fingers up / down; media commands (mute, play/pause, next /
  previous track) for any gesture.
* Clicks now fire when the pinch opens (needed to tell a click from a drag); set
  *Pinch and hold to drag* off in Settings › Hand gestures to click on close as before.

## 0.1.0

* First release: cursor, clicks, scroll, swipes, pause, head navigation, virtual
  keyboard, calibration wizard, settings, Windows installer.
