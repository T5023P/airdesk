# Platform compatibility matrix

Legend:

* **Verified** — exercised on that platform by this build, with the evidence named.
* **Unit-tested** — code exists and is covered by mocked tests; the real device or
  session has **not** been exercised.
* **Unverified** — implemented but neither tested nor claimed.
* **Unavailable** — deliberately not supported on that platform; AIRDESK reports it
  as unavailable instead of pretending.

| Feature | Windows 11 x64 | Kali Linux X11 | Kali Linux Wayland |
|---|---|---|---|
| Camera capture (OpenCV) | **Verified** — `--camera-diagnostics`: 640×480, 30.5 FPS, real frames | Unit-tested (V4L2 path) | Unit-tested (same V4L2 path) |
| MediaPipe hand tracking | **Verified** — smoke run processed 189 frames @ 32.9 FPS | Unit-tested | Unit-tested |
| MediaPipe face / head tracking | **Verified** in earlier smoke runs | Unit-tested | Unit-tested |
| Gesture recognition + gesture log | **Verified** (real photos + synthetic sequences; live gestures recognised in test mode) | Unit-tested | Unit-tested |
| Cursor movement | **Verified** (Win32 `SendInput`) | Unverified (XTest, needs `libxtst6`) | **Unavailable** — compositor blocks XTest |
| Left / right / middle click | **Verified** | Unverified (XTest) | **Unavailable** |
| Drag and drop | **Verified** | Unverified | **Unavailable** |
| Scroll (vertical + horizontal) | **Verified** (Win32 wheel events, fractional) | Unverified (XTest buttons 4/5) | **Unavailable** |
| Keyboard injection | **Verified** (incl. Unicode text) | Unverified (XTest keysyms) | **Unavailable** |
| Modifier keys (Ctrl/Alt/Shift/Win) | **Verified** | Unverified | **Unavailable** |
| Virtual QWERTY keyboard | **Verified** (clicks into other apps, no focus steal) | Unit-tested; typing path unverified | UI works; typing **unavailable** |
| Volume up / down | **Verified** path (Win32 `VK_VOLUME_*`); real sink change not re-measured this session | Unit-tested (wpctl/pactl commands; real sink not changed on Kali) | Same as X11 (mixer tools are session-independent) |
| Mute / unmute | Same as volume | Unit-tested | Same as X11 |
| Volume level readout | **Unavailable** via multimedia keys (reported) | Unit-tested (`wpctl get-volume` / `pactl`) | Unit-tested |
| Screenshot | **Verified** (Qt `grabWindow`) | Unverified | May be blocked by the compositor |
| AIR COMMAND wheel | **Verified** (overlay rendering + allow-list; simulated actions in test mode) | Unit-tested logic; action execution per-row | Wheel works; actions that inject input **unavailable** |
| AIR MACROS (editor, store, runner) | **Verified** (editor rendered; runner unit-tested) | Unit-tested | Editor works; input actions unavailable |
| Two-hand chords | Unit-tested (state machine, debounce, cooldown) | Unit-tested | Same logic |
| Multi-monitor mapping | Unit-tested; single-monitor **verified** | Unverified (Qt geometry is reported by diagnostics) | Geometry only |
| Emergency stop button / in-app `Ctrl+Shift+G` | **Verified** | Unverified | Works (stops tracking) |
| Global `Ctrl+Alt+Shift+G` hotkey | **Verified** (Win32 `RegisterHotKey`) | **Unavailable** (reported) | **Unavailable** |
| Physical-mouse corner fail-safe | **Verified** (PyAutoGUI fail-safe) | Unverified | **Unavailable** (no pointer control) |
| Launch at login | **Verified** (HKCU Run key) | **Unavailable** (use an autostart `.desktop` file) | Same |
| Test mode / simulation | **Verified** | Unit-tested | Unit-tested |
| Camera / model diagnostics | **Verified** | Unit-tested | Unit-tested |

## What this means

* The **Windows** column is the only column with real hardware evidence.
* The **Kali** columns describe code that compiles, imports and passes mocked
  tests. They are **not** a claim that gestures control a Kali desktop — that
  requires the checklist in `docs/DEPLOYMENT_KALI.md` §6 on the laptop itself.
* Nothing here requires root, a paid API, or network access.

## Evidence commands

```powershell
# Windows
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe main.py --full-diagnostics --probe-camera
.\.venv\Scripts\python.exe main.py --smoke-test 15 --test-mode --source 0
```

```bash
# Kali (to be run on the target laptop)
./.venv/bin/python -m pytest
./.venv/bin/python main.py --full-diagnostics --probe-camera
./.venv/bin/python main.py --smoke-test 15 --test-mode --source 0
```

Record the output in the test report (`docs/TESTING_GUIDE.md`).
