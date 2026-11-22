# AIRDESK on Linux and Kali

> **See also:** [DEPLOYMENT_KALI.md](DEPLOYMENT_KALI.md) for the step-by-step
> deployment (system packages, scripts, camera, input permissions, audio, launch)
> and [PLATFORM_COMPATIBILITY.md](PLATFORM_COMPATIBILITY.md) for the per-feature
> verified/unverified matrix. This page stays as the short conceptual overview.

Windows is the development platform; **Kali Linux is the deployment target**. This
document explains what works, what is detected, and what has *not* been verified on
real Kali hardware.

> **Honesty note.** The Linux code paths are implemented and unit-tested, and the
> session/backend detection is exercised on Windows. They have **not** been run on a
> Kali machine with a live camera by the author of this build. Treat the sections
> marked “unverified” accordingly.

## 1. Install (per-user, never as root)

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv libgl1 libglib2.0-0 \
                    libxcb-cursor0 libxcb-xinerama0 libxtst6 libxkbcommon-x11-0 \
                    v4l-utils portaudio19-dev
sudo usermod -aG video "$USER"     # camera access; log out and back in
```

Create the virtual environment **as your normal user**:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py --diagnostics
```

Do **not** run AIRDESK with `sudo`. It does not need root: pointer and keyboard
injection go through XTest on X11, and multimedia keys go through the desktop's own
mechanism. The app should be launched from your graphical session.

## 2. Which session am I in?

```bash
echo "$XDG_SESSION_TYPE"     # x11 or wayland
```

AIRDESK reports this itself: `python main.py --diagnostics` prints the detected
session, the available backends and an explicit list of unsupported capabilities.

| Capability | X11 | Wayland |
|---|---|---|
| Camera / MediaPipe tracking | yes | yes |
| Cursor movement, clicks, scroll | XTest (`libxtst6`) | **not supported** — compositor blocks synthetic input |
| Keyboard injection, virtual keyboard | XTest | **not supported** |
| Volume / media keys | media keys (best effort) | **not supported** |
| Global hotkey | via the desktop shortcut mechanism | **not supported** |
| Emergency stop, test mode | yes | yes (stops tracking) |
| Air Command wheel, macros, chords | yes (same allow-list) | logic works; actions that inject input report unsupported |
| Multi-monitor mapping | yes (Qt screen geometry) | geometry only |

If a capability is unsupported, AIRDESK says so in diagnostics instead of pretending
it worked. On Wayland you can still start the app, track hands, preview video and
watch gestures being recognised in test mode.

### Running under Wayland anyway

Use an X11 session (choose “Xorg” at the login screen on Kali/GNOME/KDE), or run
XWayland-aware: the X11 backend requires `DISPLAY` to be set and only reaches X11
clients. Wayland-native applications will not receive injected input.

`ydotool` and `uinput` are detected when present; they are never required, and the
app does not attempt to install kernel modules.

## 3. Camera

```bash
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --all | head
```

* The capture backend selector in Settings is Windows-specific; on Linux OpenCV uses
  V4L2 automatically.
* Camera access requires membership of the `video` group (see above).
* If the preview is black, check that no other process (Cheese, Zoom, browser) holds
  the device.

## 4. Permissions and safety

* **Never run as root.** There is no feature that requires it.
* The emergency stop key and the Dashboard **EMERGENCY STOP** button release any
  held mouse button and stop injection immediately.
* Live input is opt-in: the app starts in test mode, and gestures do not reach the
  desktop until you turn test mode off.
* Video frames are processed in memory only; nothing is written to disk.

## 5. Packaging notes

* `gestura.spec` (PyInstaller) is Windows-oriented. On Linux, build with
  `pyinstaller gestura.spec` and verify that the `assets/` directory is bundled.
* No distribution-specific packages are required beyond the apt list above.

## 6. Verification checklist for the Kali machine

Run these on the actual target and record the output:

1. `python main.py --diagnostics` — session, backends, unsupported list.
2. `python main.py --smoke-test 8 --test-mode --source 0 --screenshot kali.png` —
   frames, FPS, latency, camera index.
3. `pytest -q` — the full suite on Linux.
4. Real session, test mode **off**: cursor movement, click, drag, scroll, volume,
   page navigation, virtual keyboard, Air Command wheel, one macro, monitor switch,
   emergency stop, application quit (mouse button released).
5. Wayland session: confirm the app starts, tracks and reports unsupported actions.

Anything that fails should be recorded in the issue tracker with the diagnostics
output and the compositor/desktop version.
