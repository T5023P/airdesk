# AIRDESK on Windows 11 — development guide

Windows 11 (x64) is the **development** machine. Kali Linux is the runtime target.
Everything below is per-user: no administrator rights, no global Python packages,
no paid service, no cloud inference.

> Verified on this build: Python 3.11.9 in `F:\OPENCV\.venv`, 226 tests
> (219 passed, 7 skipped), a real webcam stream at ~30 FPS, and the consolidated
> diagnostics. See [TESTING_GUIDE.md](TESTING_GUIDE.md) for the current report.

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Windows 10/11, 64-bit | The only platform where the input backend is fully verified. |
| Python 3.11 or 3.12, 64-bit | `pyproject.toml` declares `>=3.11,<3.13`. MediaPipe has no 3.13 wheel. |
| Git for Windows | Needed for the branch/pull workflow, not to run the app. |
| A webcam | Built-in or USB. Only opened when you press **Start** (or in diagnostics). |
| ~1.5 GB disk | Qt, OpenCV, MediaPipe and the two bundled models. |

## 2. Setup

From the repository root (`F:\OPENCV`):

```powershell
.\scripts\bootstrap_windows.ps1
```

The script checks the platform, finds a supported Python, creates `.venv`,
upgrades pip, installs `requirements.txt` (pinned, tested set) and
`requirements-dev.txt` (pytest), installs the project itself in editable mode
(`pip install -e . --no-deps`), then verifies the imports and the bundled
MediaPipe models with their pinned SHA-256.

Useful flags:

```powershell
.\scripts\bootstrap_windows.ps1 -Recreate   # delete .venv and rebuild
.\scripts\bootstrap_windows.ps1 -SkipDev    # runtime dependencies only
.\scripts\bootstrap_windows.ps1 -Python C:\Python312\python.exe
```

If PowerShell blocks the script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_windows.ps1
```

## 3. Run

```powershell
.\scripts\run_airdesk_windows.ps1                     # normal start (test mode on by default)
.\scripts\run_airdesk_windows.ps1 --start             # start tracking immediately
.\scripts\run_airdesk_windows.ps1 --live              # real control, no test mode
.\scripts\run_airdesk_windows.ps1 --page studio
.\scripts\run_airdesk_windows.ps1 --source 1          # second camera
```

Equivalent direct form:

```powershell
.\.venv\Scripts\python.exe main.py --start
```

The app starts in **test mode**: gestures are recognised and logged, nothing is
sent to the desktop. Turn *Test mode* off on the Dashboard only when you want
real input.

## 4. Webcam testing

```powershell
# Opens the camera for ~2 s and prints resolution + measured FPS
.\.venv\Scripts\python.exe main.py --camera-diagnostics

# Everything at once, including the camera
.\.venv\Scripts\python.exe main.py --full-diagnostics --probe-camera
.\.venv\Scripts\python.exe main.py --full-diagnostics --probe-camera --json
```

A device being listed does **not** prove capture. `--camera-diagnostics` reports
the negotiated resolution, the number of frames actually read and the measured
FPS, or the exact failure (busy device, permission, no frames). It exits non-zero
when no camera delivered frames, so it is usable in a script.

Scripted end-to-end check (real camera + real pipeline + window screenshot):

```powershell
.\.venv\Scripts\python.exe main.py --smoke-test 15 --test-mode --source 0 --screenshot out.png
```

`--smoke-test` prints JSON (`frames`, `fps`, `latency_ms`, `status`) and exits
non-zero when zero frames were processed. Model loading takes ~9–10 s, so give it
at least 15 s.

Before launching, close Teams/Zoom/Camera: Windows allows one capture owner per
device. If the preview is black, check **Settings → Privacy & security → Camera**
and enable *Let desktop apps access your camera*.

## 5. Tests

```powershell
.\.venv\Scripts\python.exe -m pytest                 # full suite
.\.venv\Scripts\python.exe -m pytest tests/test_platform_support.py -v
.\.venv\Scripts\python.exe -m pytest -k "camera or audio or backend"
```

GUI tests run headless (`QT_QPA_PLATFORM=offscreen`, set by `tests/conftest.py`).
Real OS-input tests are opt-in and skipped by default:

```powershell
$env:GESTURA_OS_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest tests/test_os_integration.py -v
Remove-Item Env:\GESTURA_OS_TESTS
```

Note: `pytest -q` twice (`-qq`) suppresses the summary line; use plain `pytest`
or `--tb=short` to see counts.

## 6. Updating dependencies

`pyproject.toml` holds compatible ranges; `requirements.txt` holds the exact
tested pins. To change a version:

1. Edit `requirements.txt` (one change at a time).
2. `.\scripts\bootstrap_windows.ps1` (or `pip install -r requirements.txt`).
3. Run `pytest` and the camera diagnostics.
4. Confirm the change also has a wheel for Linux (`pip download --only-binary=:all:
   --platform manylinux2014_x86_64 --python-version 3.12 <pkg>`), because Kali
   must run the same pins.
5. Record the change in `CHANGELOG.md`.

Do not regenerate a lockfile blindly and do not upgrade every package at once:
MediaPipe, OpenCV and Qt must stay mutually compatible (MediaPipe already depends
on `opencv-contrib-python`; installing `opencv-python` alongside it breaks `cv2`).

## 7. Git workflow (Windows → Kali)

The repository currently has one remote (`origin` → the upstream Gestura
project) and a dirty working tree from the AIRDESK work. Do **not** push to
upstream. Create your own private repository and a dedicated branch:

```powershell
git switch -c airdesk-custom        # local branch for the customisation
git add -A
git commit -m "AIRDESK: portability, diagnostics and Kali deployment"
git remote add airdesk https://github.com/<you>/airdesk.git
git push -u airdesk airdesk-custom
```

Then on Kali:

```bash
git clone --branch airdesk-custom https://github.com/<you>/airdesk.git ~/airdesk
cd ~/airdesk && ./scripts/bootstrap_kali.sh --probe-camera
```

After further work on Windows:

```powershell
git add -A; git commit -m "…"; git push
```

and on Kali `git pull`. Always inspect `git remote -v` before adding or changing
a remote: `origin` must keep pointing at `Raphzaf/gestura` for attribution and
upstream history.

## 8. Where things live

| Path | Purpose |
|---|---|
| `%APPDATA%\Gestura\settings.json` | Settings (organisation name intentionally unchanged so existing profiles survive). |
| `%LOCALAPPDATA%\Gestura\logs\gestura.log` | Rotating log (critical errors, camera status). |
| `Pictures\AIRDESK\` | Screenshots from AIR COMMAND. |
| `gestura/assets/models/` | Bundled `hand_landmarker.task` + `face_landmarker.task` (SHA-256 pinned in `gestura/vision/models.py`). |
