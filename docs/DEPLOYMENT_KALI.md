# AIRDESK on Kali Linux — deployment guide

Kali Linux is the runtime target. Development happens on Windows 11; the two
machines share one codebase, one virtual environment layout and the same pins.

> **Read this first.** Everything below is implemented and covered by mocked unit
> tests on Windows. The Linux-specific *behaviour* (X11 injection, wpctl/pactl,
> V4L2 capture, Wayland limits) has **not** been executed on Kali hardware by this
> build. `docs/PLATFORM_COMPATIBILITY.md` marks each feature as verified,
> unit-tested or unverified — trust that table, not marketing.

## 1. Supported desktop sessions

| Session | Detection | Input injection | Recommendation |
|---|---|---|---|
| **X11 / Xorg** | `XDG_SESSION_TYPE=x11`, `DISPLAY=:0` | XTest through PyAutoGUI (needs `libxtst6`) | **Use this.** Full functionality. |
| **Wayland** (GNOME/KDE default) | `XDG_SESSION_TYPE=wayland`, `WAYLAND_DISPLAY` | Blocked for normal apps. Optional `ydotool` path (experimental, opt-in) | Tracking and test mode only, unless you accept the experimental backend. |
| TTY / SSH | no `DISPLAY`, no `WAYLAND_DISPLAY` | None | Not supported for the GUI; only `--full-diagnostics` is useful. |

Choose **"Xorg"** (or "Kali Linux (X11)") in the session menu at the login screen.
AIRDESK detects the session at startup and reports it; it never assumes X11.

## 2. System dependencies

Python packages are installed **only** into the project virtual environment.
System packages are needed for camera access, Qt and X11:

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev git \
                    libgl1 libglib2.0-0 libegl1 \
                    libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 \
                    libxkbcommon-x11-0 libxkbcommon0 libdbus-1-3 \
                    libxtst6 v4l-utils \
                    wireplumber pipewire-bin \
                    xdotool
```

Notes:

* `libxtst6` is what makes X11 pointer/keyboard injection possible. Without it,
  AIRDESK still runs but reports input as unavailable.
* `v4l-utils` provides `v4l2-ctl` for camera inspection.
* `wireplumber` provides `wpctl`; if you run PulseAudio instead, install
  `pulseaudio-utils` for `pactl`. AIRDESK detects whichever exists.
* MediaPipe and OpenCV ship manylinux wheels; no compiler is normally required.
  If pip wants to build something, install `build-essential python3-dev`.
* Python must be **3.11 or 3.12**. Kali rolling sometimes ships 3.13 first;
  install a supported interpreter (`python3.12 python3.12-venv`) before bootstrapping.

## 3. Transfer the project

Either method works; both keep `LICENSE`, `UPSTREAM.md` and the models.

**A — Git (recommended for updates)**

```bash
git clone --branch airdesk-custom https://github.com/<you>/airdesk.git ~/airdesk
cd ~/airdesk
```

**B — Archive (air-gapped / quick test)**

On Windows:

```powershell
.\scripts\make_source_archive.sh      # or: bash scripts/make_source_archive.sh
# → dist/airdesk-src-<date>.tar.gz  (no .venv, no __pycache__, no logs)
```

Copy the file to Kali, then:

```bash
mkdir -p ~/airdesk && tar -xzf airdesk-src-*.tar.gz -C ~/airdesk && cd ~/airdesk
```

Never copy a Windows `.venv` to Linux: its binaries and absolute paths do not
work there. The bootstrap script always builds a fresh `.venv`.

## 4. Install

```bash
cd ~/airdesk
chmod +x scripts/*.sh
./scripts/bootstrap_kali.sh --probe-camera
```

The script:

1. refuses to run as root and detects Kali/Debian + architecture;
2. verifies Python 3.11/3.12 and `venv`;
3. reports missing system tools with the exact `apt` command;
4. checks `/dev/video*` and `video` group membership (and offers to run
   `sudo usermod -aG video "$USER"` only after an explicit `y`);
5. creates `.venv`, upgrades pip, installs `requirements.txt` +
   `requirements-dev.txt`, then `pip install -e . --no-deps`;
6. imports OpenCV, MediaPipe, PySide6, pydantic and AIRDESK;
7. verifies both landmarker models against their pinned SHA-256;
8. verifies `.venv/bin/airdesk` and prints `--diagnostics`;
9. optionally opens the camera for ~2 s and reports real frames/FPS.

Flags: `--recreate`, `--no-dev`, `--probe-camera`.

## 5. Camera access

```bash
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --all | head -20
groups | tr ' ' '\n' | grep video        # must print "video"
```

* Membership of the `video` group takes effect only after a full log out/in.
* Only one process may capture a device. Close Cheese/OBS/Zoom/browser tabs.
* Run `./.venv/bin/python main.py --camera-diagnostics` — it reports the
  negotiated resolution and the **measured** FPS, or why opening failed.
* Some laptops expose both a camera and an IR/metadata node (`/dev/video0`,
  `/dev/video1`). If index 0 fails, try `--source 1` and set the index in Settings.

## 6. Input permissions (the critical part)

| Session | What happens | What you need |
|---|---|---|
| X11 | PyAutoGUI → XTest → `libXtst` | `libxtst6`; nothing else. No root. |
| Wayland | compositor refuses synthetic input | An X11 session, or the experimental `ydotool` path |

**Always start with X11.** Then verify, with test mode **off**:

1. cursor movement follows the index finger;
2. left click, right click, drag and drop;
3. vertical and horizontal scroll;
4. keyboard input and the Ctrl/Alt/Shift modifiers;
5. virtual keyboard typing into a text field;
6. **EMERGENCY STOP** releases any held button and stops injection;
7. quitting the app never leaves a modifier or mouse button held.

### Optional Wayland path (experimental, unverified)

`ydotool` writes to `/dev/uinput` through its own user daemon, so AIRDESK never
needs root:

```bash
sudo apt install -y ydotool
sudo systemctl enable --now ydotool        # package-provided unit on recent Kali
# or, if the unit is missing:
#   sudo ydotoold &                        # not recommended long-term
systemctl --user enable --now ydotool      # where the package does not provide it
ydotool mousemove --absolute 200 200       # sanity check
```

Then launch with the backend explicitly requested:

```bash
AIRDESK_INPUT_BACKEND=ydotool ./scripts/run_airdesk_kali.sh
```

AIRDESK never selects it automatically. Its command syntax differs between
ydotool versions, scrolling is unverified, and `--full-diagnostics` marks it
`experimental: true`. If it misbehaves, go back to an X11 session.

**Never** run AIRDESK with `sudo`, add yourself to groups you do not need, or set
`uinput` world-writable. There is no feature that requires root.

## 7. Audio

AIRDESK detects the mixer at startup instead of assuming one:

| Tool | Sound server | Used for |
|---|---|---|
| `wpctl` | PipeWire / WirePlumber (Kali default) | volume up/down (±5 %), mute toggle, level readout |
| `pactl` | PulseAudio-compatible | same |
| multimedia keys | X11 fallback | volume/mute when no tool is found |

Verify manually:

```bash
wpctl status | head
wpctl get-volume @DEFAULT_AUDIO_SINK@
wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+
wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
```

The three-finger volume gesture and the AIR COMMAND *Volume +/-* entries go
through this service, so they change the real sink. `--full-diagnostics` prints
the backend, the current volume and the mute state.

## 8. Other system controls

| Control | Implementation | Notes |
|---|---|---|
| Screenshot | Qt `grabWindow(0)` → `~/Pictures/AIRDESK/` | Works on X11; on Wayland the compositor may block it. |
| Launch browser / calculator / file manager | fixed argv: `webbrowser`, `gnome-calculator`/`kcalc`/`galculator`/`xcalc`, `xdg-open ~` | Missing apps are reported, never guessed. |
| Brightness | not implemented | Use your desktop's own keys; no safe portable CLI without extra packages. |
| App switching / window snap | `alt+tab`, `super+←/→` | Depends on the desktop's shortcuts; KDE/GNOME accept them. |
| Global hotkey | Windows only | On Linux use the EMERGENCY STOP button, the in-app Ctrl+Shift+G, the open-palm gesture, or the physical-mouse corner fail-safe. |

## 9. Diagnostics

```bash
./.venv/bin/python main.py --diagnostics                  # session + input capabilities
./.venv/bin/python main.py --full-diagnostics             # versions, models, input, audio, displays
./.venv/bin/python main.py --full-diagnostics --json      # machine-readable
./.venv/bin/python main.py --full-diagnostics --probe-camera
./.venv/bin/python main.py --camera-diagnostics
```

Nothing personal is collected: no usernames beyond the config path, no camera
frames saved, no network calls.

## 10. Launch and shut down

```bash
./scripts/run_airdesk_kali.sh                # prints diagnostics, then starts
./scripts/run_airdesk_kali.sh --start        # start tracking immediately
./scripts/run_airdesk_kali.sh --test-mode    # observe gestures without input
./scripts/run_airdesk_kali.sh --no-diagnostics
```

Shut down with the window close button (settings are saved), or `Ctrl+Q`. Press
**EMERGENCY STOP** first if a button may be held. Closing the window always
releases mouse buttons and modifiers and releases the camera — verify with:

```bash
fuser -v /dev/video0        # must show nothing after the app exits
```

## 11. Troubleshooting quick table

| Symptom | Cause | Fix |
|---|---|---|
| `No matching distribution found for mediapipe` | Unsupported Python | Install Python 3.12 and re-run the bootstrap |
| `qt.qpa.plugin: could not load the Qt platform plugin "xcb"` | Missing xcb libs | Install the `libxcb-*` list in §2 |
| `Input: Wayland blocks synthetic input` | Wayland session | Log out, choose Xorg |
| Cursor moves but nothing clicks | App is in test mode | Turn *Test mode* off on the Dashboard |
| Camera opens then "no frames" | Device held elsewhere | Close other camera apps; `fuser -v /dev/video0` |
| Volume gesture does nothing | No `wpctl`/`pactl` | Install `wireplumber` or `pulseaudio-utils` |
| Audio reads `media-keys` fallback | No mixer tool found | Install PipeWire/WirePlumber |
| `Permission denied` on `/dev/video0` | Not in `video` group | `sudo usermod -aG video "$USER"`, log out/in |

Longer version: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
