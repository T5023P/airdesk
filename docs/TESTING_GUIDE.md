# AIRDESK testing guide

Three different kinds of evidence, never mixed:

| Layer | What it proves | Where it runs |
|---|---|---|
| **Automated unit/UI tests** | Logic, validation, allow-lists, mapping, mocked OS boundaries | `pytest`, any machine |
| **Device integration** | A real camera/input device exists and behaves | Only on hardware, per platform |
| **Manual session test** | Gestures really control the desktop | A person, in a live session |

A mocked Linux test **never** proves Kali compatibility. Only a run on the Kali
laptop does.

## 1. Automated suite

```powershell
# Windows
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest tests/test_platform_support.py -v
```

```bash
# Kali
./.venv/bin/python -m pytest
```

GUI tests are headless: `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`
unless `GESTURA_OS_TESTS=1`. Real OS-input tests are skipped by default.

```
$env:GESTURA_OS_TESTS = "1"          # PowerShell
.\.venv\Scripts\python.exe -m pytest tests/test_os_integration.py -v
```

### What the portability tests cover (`tests/test_platform_support.py`)

* session detection: Windows, `XDG_SESSION_TYPE`, `DISPLAY`, `WAYLAND_DISPLAY`,
  and the "no display" case;
* model resolution from any working directory, missing model, checksum mismatch;
* camera open failure, opens-but-no-frames, driver exception, guaranteed release,
  report formatting and JSON;
* audio detection order (`wpctl` → `pactl` → multimedia keys), exact argv for
  volume/mute/status, parsing, and failure reporting;
* input capability detection for Windows/X11/Wayland, and that `select_backend`
  refuses to fake Wayland input;
* `ydotool` command construction (experimental backend);
* mouse/keyboard dispatch, emergency release of held buttons and modifiers;
* AIR COMMAND volume routing through the audio service;
* the consolidated report (`--full-diagnostics`) serialising to JSON.

All of this is mocked. It is a regression net, not a hardware certificate.

## 2. Device integration checks (must be run on the machine)

```bash
# camera: real frames + measured FPS, non-zero exit if nothing opened
./.venv/bin/python main.py --camera-diagnostics

# camera + models + input + audio in one report
./.venv/bin/python main.py --full-diagnostics --probe-camera

# 15 s pipeline run with a real camera, prints JSON stats
./.venv/bin/python main.py --smoke-test 15 --test-mode --source 0 --screenshot smoke.png
```

`--smoke-test` exits non-zero when zero frames were processed. Model loading
takes ~9–10 s, so never run it for less than 12 s.

Then, with **test mode off**, perform the manual checklist in
`DEPLOYMENT_KALI.md` §6: cursor, left/right click, drag, scroll, keyboard,
modifiers, virtual keyboard, emergency stop, and quit-while-dragging.

After the app exits, the camera must be free:

```bash
fuser -v /dev/video0        # no output expected
```

## 3. Report template

Copy this into the issue or the handover note and fill it in with real output.

```markdown
### AIRDESK test report — <date> — <machine>

Environment
- OS / version:
- Desktop session (XDG_SESSION_TYPE / Windows):
- Python / AIRDESK version:
- Camera model / index:

Windows verified
- [ ] pytest: ____ passed, ____ skipped, ____ failed
- [ ] --full-diagnostics: input=____ audio=____
- [ ] --camera-diagnostics: ____x____ @ ____ FPS, ____ frames
- [ ] --smoke-test 15: ____ frames, ____ FPS, ____ ms latency
- [ ] live session: cursor / click / drag / scroll / keyboard / virtual keyboard
- [ ] emergency stop and quit release all buttons

Kali unit-tested (mocked, on Windows)
- [ ] platform detection, model verification, camera error paths
- [ ] audio detection and command construction
- [ ] backend selection and Wayland refusal

Kali hardware-tested (on the laptop)
- [ ] pytest on Kali: ____ passed, ____ skipped, ____ failed
- [ ] camera: ____x____ @ ____ FPS
- [ ] X11 injection: pointer / click / drag / scroll / keys / modifiers
- [ ] audio: real volume change and mute verified with wpctl/pactl
- [ ] AIR COMMAND end-to-end, one macro, one chord
- [ ] emergency stop, clean shutdown, camera released
- [ ] Wayland: app starts, tracks, reports unsupported actions

Unsupported / unverified on this build
- Wayland synthetic input (experimental ydotool only)
- Linux global emergency hotkey
- Brightness control
```

## 4. Rules

* Never mark a hardware row as passed from a mocked test.
* Never claim volume works without observing a real level change.
* Never claim camera support without frames actually read.
* Failed tests are reported, not deleted or skipped to make a run green.
