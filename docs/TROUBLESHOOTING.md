# Troubleshooting

## The camera does not open

* **Windows privacy**: Settings › Privacy & security › Camera → allow camera access
  and "Let desktop apps access your camera".
* Close other apps using the camera (Teams, Zoom, the Camera app).
* Settings › Camera › **Detect cameras** (stop the camera first) and pick the right one.
* Try **Capture backend** `msmf` instead of `auto` (DirectShow) or vice versa.
* Unplugging the camera while running shows "Camera lost"; Gestura reconnects
  automatically every 2 seconds.

## Low FPS or high latency

* Gesture Studio shows FPS, latency and per-model times.
* Turn off **Face / head tracking** if you don't use Navigation mode (the face
  model is also skipped automatically when no visible page or mode needs it).
* Keep capture at 640×480; higher resolutions cost CPU without improving tracking.
* Laptops: plug in power — Windows battery saver throttles the CPU.

## Cursor is jittery / lags

* Jittery: lower **Smoothing** (`smoothing_min_cutoff`) or raise **Dead zone**.
* Laggy on fast moves: raise **Responsiveness to fast moves** (`smoothing_beta`).
* Hard to reach screen edges: shrink the **Active region** or raise **Cursor speed**.

## Clicks don't register, or happen by accident

* Run the **Calibration wizard** — the pinch step learns your thresholds.
* Watch the *Thumb–index* meter in Gesture Studio: the bar must cross the left tick
  (closes) and come back past the right tick (opens).
* Accidental clicks: lower `pinch_on_ratio`; raise `pinch_min_frames`.

## Head gestures fire when I just look around

Raise the thresholds (Settings › Head gestures), raise *Hold beyond threshold*,
and re-run the calibration so "neutral" matches how you sit. Head gestures only
fire after returning to neutral, so a sustained look at a second monitor fires at
most once — raise *Turn threshold* if that is still too sensitive.

## Some windows ignore Gestura's input

* **Windows UIPI**: apps running *as administrator* (and Task Manager) ignore
  synthetic input from non-elevated programs. Run Gestura as administrator to
  control them — only if you trust that setup.
* The **UAC prompt, lock screen and Ctrl+Alt+Del screen** run on the secure desktop,
  which no normal application can control. This is a Windows security boundary.
* Games using raw input or anti-cheat may ignore synthetic mouse/keyboard input.

## The virtual keyboard types into the wrong window

The keyboard never takes focus, so keys go to the window that had focus before.
Click (pinch) into the target text field first, then type. Keys are not sent while
**test mode** or an **emergency stop** is active (they still appear in the
keyboard header).

## Emergency stop

Top-bar button, `Ctrl+Shift+G` (in Gestura), `Ctrl+Alt+Shift+G` (system-wide on
Windows), or move the *physical* mouse into any screen corner. Clear it with
**Clear emergency stop** on the Dashboard.

## Settings were reset

If `settings.json` is invalid, Gestura backs it up as
`settings.invalid-<timestamp>.json` next to it and starts with defaults.
Location: `%APPDATA%\Gestura\settings.json` (Windows), `~/.config/gestura/settings.json` (Linux).

## Linux: `libEGL.so.1: cannot open shared object file`

MediaPipe's native library needs EGL: `sudo apt-get install libegl1 libgles2`.
Qt also needs `libxcb-cursor0` for its xcb platform plugin.

## Antivirus flags `Gestura.exe`

Unsigned PyInstaller executables that inject input are sometimes flagged
heuristically. Build from source, or code-sign the executable for distribution.

---

# AIRDESK cross-platform troubleshooting (Windows ↔ Kali)

Start with the report, not with guesses:

```bash
airdesk --full-diagnostics --probe-camera
airdesk --full-diagnostics --json > airdesk-report.json
```

## Setup / installation

**`bootstrap_windows.ps1` cannot be loaded because running scripts is disabled**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_windows.ps1
```

**Windows: `No module named 'mediapipe'` or `'PySide6'` after setup**

The script failed part-way. Re-run with a clean environment and read the first
pip error:

```powershell
.\scripts\bootstrap_windows.ps1 -Recreate
```

**Kali: `No matching distribution found for mediapipe`**

The interpreter is outside the supported range (3.11–3.12). Check:

```bash
python3 -V
```

Install a supported one (`sudo apt install python3.12 python3.12-venv`) and
re-run `./scripts/bootstrap_kali.sh --recreate`.

**Kali: `error: externally-managed-environment`**

You are installing with the system pip. Activate the project environment first:

```bash
source .venv/bin/activate && pip install -r requirements.txt
```

Never use `--break-system-packages` and never `sudo pip`.

**`qt.qpa.plugin: could not load the Qt platform plugin "xcb"`**

```bash
sudo apt install -y libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxkbcommon-x11-0
```

Then confirm `echo $DISPLAY` is non-empty and that you are in a graphical session.

**`libEGL.so.1: cannot open shared object file`**

```bash
sudo apt install -y libegl1 libgl1 libglib2.0-0
```

## Camera

**`--camera-diagnostics` says "could not open /dev/video0"**

```bash
v4l2-ctl --list-devices
fuser -v /dev/video0          # who else holds it?
groups | tr ' ' '\n' | grep video
```

Add yourself to `video` (`sudo usermod -aG video "$USER"`) and **log out/in**.
Some laptops need the camera enabled in firmware (Fn key or BIOS).

**"opened but delivered no frames"**

The driver accepted the open but rejected the stream: another process owns the
device, or the requested format is unsupported. Close other camera apps, then try
another index (`--source 1`) and a lower resolution in Settings.

**Windows: preview is black**

Settings → Privacy & security → Camera → enable *Camera access* and *Let desktop
apps access your camera*. Close Teams/Zoom/Camera (one capture owner per device).

## Input

**Kali: cursor moves but nothing is typed/clicked**

Check the session and the library:

```bash
 echo "$XDG_SESSION_TYPE"      # must be x11
ldconfig -p | grep Xtst        # must list libXtst
```

On Wayland, XTest is blocked by design; use an Xorg session. AIRDESK reports the
limitation in `--full-diagnostics` instead of failing silently.

**Wayland: `ydotool` does not move the pointer**

`ydotool` needs its daemon and `/dev/uinput` access:

```bash
systemctl status ydotoold 2>/dev/null || systemctl --user status ydotool
ydotool mousemove --absolute 300 300
```

If that test fails, the problem is ydotool, not AIRDESK. This backend is
**experimental and unverified**; prefer an X11 session.

**Left mouse button stuck down after a crash**

Click once with the physical mouse. AIRDESK releases buttons on stop, pause and
emergency stop; a hard kill cannot. Report it with the log file.

## Audio

**Volume gesture does nothing on Kali**

```bash
command -v wpctl pactl
wpctl get-volume @DEFAULT_AUDIO_SINK@
```

If neither tool exists, install `wireplumber` (PipeWire) or `pulseaudio-utils`.
AIRDESK then reports `audio.backend = none` in diagnostics rather than pretending.

**Volume changes but the report shows no level**

On Windows the multimedia-key API has no readout; that is expected and reported
as a note, not a failure.

## Models

**`MediaPipe model 'hand_landmarker.task' not found`**

The bundled models live in `gestura/assets/models/`. Re-fetch them:

```bash
./.venv/bin/python scripts/download_models.py
```

Never copy models between machines by hand without checking the SHA-256 printed
by `--full-diagnostics`; a different model version changes recognition results.

## Transfer

**Archive is huge / tests fail on Kali after unpacking**

A virtual environment travelled with it. Rebuild the archive with
`./scripts/make_source_archive.sh` (it excludes `.venv`, caches and logs) and run
`./scripts/bootstrap_kali.sh` on the Linux side.

**`git push` rejected / wrong remote**

```bash
git remote -v     # origin must stay Raphzaf/gestura; push to your own remote
```
