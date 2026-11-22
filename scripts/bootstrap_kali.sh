#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# AIRDESK — Kali Linux / Debian bootstrap.
#   ./scripts/bootstrap_kali.sh              # create/refresh .venv and verify
#   ./scripts/bootstrap_kali.sh --recreate    # delete .venv first
#   ./scripts/bootstrap_kali.sh --no-dev      # runtime dependencies only
#   ./scripts/bootstrap_kali.sh --probe-camera  # also open the webcam for ~2 s
#
# Rules enforced here:
#   * never run as root, never `sudo pip`, never --break-system-packages
#   * Python packages only inside .venv
#   * system packages are only *reported* with the exact apt command; the one
#     privileged change (adding you to the `video` group) asks first and runs it
#     directly with sudo, never silently.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

RECREATE=0
WITH_DEV=1
PROBE_CAMERA=0
for arg in "$@"; do
  case "$arg" in
    --recreate) RECREATE=1 ;;
    --no-dev) WITH_DEV=0 ;;
    --probe-camera) PROBE_CAMERA=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

step()  { printf '\n==> %s\n' "$1"; }
ok()    { printf '  OK  %s\n' "$1"; }
warn()  { printf '  !!  %s\n' "$1"; }
fail()  { printf '\nERROR: %s\n' "$1" >&2; exit 1; }
apt_hint() { printf '      sudo apt install -y %s\n' "$1"; }

step "AIRDESK Kali Linux bootstrap"
printf '    project: %s\n' "$PROJECT_ROOT"

# ------------------------------------------------------------------ 1. session
if [[ "${EUID}" -eq 0 ]]; then
  fail "Do not run this as root. AIRDESK never needs root; log in as your normal user."
fi
ok "running as $(id -un) (uid ${EUID})"

if [[ ! -r /etc/os-release ]]; then
  warn "/etc/os-release missing; cannot confirm the distribution."
else
  # shellcheck disable=SC1091
  . /etc/os-release
  DISTRO="${ID:-unknown}"
  LIKE="${ID_LIKE:-}"
  if [[ "$DISTRO" == "kali" ]]; then
    ok "Kali Linux detected ($NAME $VERSION_ID)"
  elif [[ "$DISTRO" == "debian" || "$LIKE" == *debian* || "$LIKE" == *ubuntu* ]]; then
    ok "Debian-family distribution detected ($NAME $VERSION_ID)"
  else
    warn "Not Kali/Debian ($DISTRO). The instructions below assume apt; adapt them."
  fi
fi

ARCH="$(uname -m)"
ok "architecture: ${ARCH}  kernel: $(uname -r)"
case "$ARCH" in
  x86_64|aarch64) ;;
  *) warn "Untested architecture ${ARCH}. MediaPipe and OpenCV wheels are published for x86_64/aarch64." ;;
esac

step "Desktop session"
SESSION_TYPE="${XDG_SESSION_TYPE:-unknown}"
printf '    XDG_SESSION_TYPE=%s  XDG_CURRENT_DESKTOP=%s\n' "$SESSION_TYPE" "${XDG_CURRENT_DESKTOP:-unknown}"
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  warn "No DISPLAY / WAYLAND_DISPLAY: running from SSH? Launch AIRDESK from the graphical session."
fi
if [[ "$SESSION_TYPE" == "wayland" ]]; then
  warn "Wayland session: synthetic input is blocked by the compositor."
  warn "Choose an X11 ('Xorg') session at the login screen for full mouse/keyboard control."
fi

# ------------------------------------------------------------------- 2. Python
step "Checking Python (project requires >=3.11,<3.13)"
find_python() {
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if (3, 11) <= sys.version_info[:2] <= (3, 12) else 1)
PY
      then echo "$candidate"; return 0; fi
    fi
  done
  return 1
}
PYTHON_BIN="$(find_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  HAVE="$(python3 -V 2>&1 || echo 'python3 missing')"
  printf '%s\n' "$HAVE"
  printf '      AIRDESK supports Python 3.11 and 3.12 (see requires-python in pyproject.toml).\n'
  printf '      Install a supported interpreter, then re-run:\n'
  apt_hint "python3.12 python3.12-venv python3.12-dev"
  exit 1
fi
ok "$("$PYTHON_BIN" -V) at $(command -v "$PYTHON_BIN")"

if ! "$PYTHON_BIN" -c "import venv" >/dev/null 2>&1; then
  fail "python3-venv is missing. Install it and re-run:  sudo apt install -y $(basename "$PYTHON_BIN")-venv"
fi
ok "venv module available"

# --------------------------------------------------- 3. system tools (reported)
step "Checking system tools (report only)"
MISSING_APT=()
check_tool() {
  local tool="$1" package="$2" required="$3"
  if command -v "$tool" >/dev/null 2>&1; then
    ok "$tool → $(command -v "$tool")"
  else
    if [[ "$required" == "required" ]]; then
      warn "$tool missing (required for this stage)"
      MISSING_APT+=("$package")
    else
      warn "$tool missing (optional: $package)"
    fi
  fi
}
check_tool git git required
check_tool v4l2-ctl v4l-utils optional
check_tool wpctl wireplumber optional
check_tool pactl pulseaudio-utils optional
check_tool xdotool xdotool optional
check_tool ydotool ydotool optional
check_tool gnome-calculator gnome-calculator optional

# ------------------------------------------------------------------ 4. camera
step "Checking video devices"
if compgen -G "/dev/video*" >/dev/null; then
  for dev in /dev/video*; do
    printf '    %s %s\n' "$dev" "$(ls -l "$dev" 2>/dev/null | awk '{print $1, $3, $4}')"
  done
  ok "video device nodes present"
else
  warn "No /dev/video* nodes. Check the webcam is enabled (some laptops have a hardware/BIOS switch)."
fi
if id -nG "$USER" | tr ' ' '\n' | grep -qx video; then
  ok "user '$USER' is in the 'video' group"
else
  warn "user '$USER' is NOT in the 'video' group: OpenCV may not open the camera."
  printf '      Fix (takes effect after a full log out / log in):\n'
  printf '      sudo usermod -aG video %s\n' "$USER"
  if [[ -t 0 ]]; then
    read -r -p "      Run that command now with sudo? [y/N] " answer || answer=""
    if [[ "${answer,,}" == "y" ]]; then
      sudo usermod -aG video "$USER" && ok "added; log out and back in before launching AIRDESK"
    else
      warn "skipped — you can run it later; camera access may fail until then"
    fi
  fi
fi

# ---------------------------------------------------------------- 5. venv+install
VENV="$PROJECT_ROOT/.venv"
VPY="$VENV/bin/python"
if [[ "$RECREATE" -eq 1 && -d "$VENV" ]]; then
  step "Removing the existing virtual environment (--recreate)"
  rm -rf "$VENV"
fi
if [[ ! -x "$VPY" ]]; then
  step "Creating .venv with $PYTHON_BIN"
  "$PYTHON_BIN" -m venv "$VENV"
else
  ok "reusing $VENV"
fi
[[ -x "$VPY" ]] || fail "The virtual environment has no interpreter at $VPY"

step "Installing pinned runtime dependencies"
"$VPY" -m pip install --upgrade pip
"$VPY" -m pip install -r requirements.txt || fail "pip install failed (see the error above; a wheel may be missing for $ARCH)."

if [[ "$WITH_DEV" -eq 1 ]]; then
  step "Installing test dependencies"
  "$VPY" -m pip install -r requirements-dev.txt || fail "test dependency installation failed"
fi

step "Installing AIRDESK in editable mode"
"$VPY" -m pip install -e . --no-deps || fail "editable install failed"

# -------------------------------------------------------------- 6. verification
step "Verifying imports"
"$VPY" - <<'PY' || fail "One or more imports failed — read the traceback above."
import sys
import cv2, mediapipe, numpy, pydantic
from PySide6 import QtWidgets
import gestura
print(f"    airdesk {gestura.__version__} | python {sys.version.split()[0]}")
print(f"    opencv {cv2.__version__} | mediapipe {mediapipe.__version__} | numpy {numpy.__version__}")
print(f"    pyside6 ok ({QtWidgets.__name__}) | pydantic {pydantic.__version__}")
print(f"    gestura package: {gestura.__file__}")
PY
ok "OpenCV / MediaPipe / PySide6 / pydantic import"

step "Verifying the bundled MediaPipe models"
if ! "$VPY" - <<'PY'
from gestura.vision.models import verify_models
bad = 0
for check in verify_models():
    state = "ok" if check.usable else (check.detail or "unusable")
    print(f"    {check.name}: {check.size / 1_048_576:.1f} MiB {state}")
    bad += 0 if check.usable else 1
raise SystemExit(1 if bad else 0)
PY
then
  warn "A model is missing or does not match its pinned checksum."
  printf '      Fix: %s scripts/download_models.py\n' "$VPY"
  printf '      Model source + licence: UPSTREAM.md\n'
  exit 1
fi
ok "hand + face landmarker models verified"

step "Verifying the launcher"
if [[ -x "$VENV/bin/airdesk" ]]; then
  ok "$VENV/bin/airdesk"
else
  warn "$VENV/bin/airdesk missing; use '$VPY main.py' instead"
fi

step "Platform diagnostics"
"$VPY" main.py --diagnostics || warn "diagnostics reported a problem (see above)"

if [[ "$PROBE_CAMERA" -eq 1 ]]; then
  step "Camera probe (opens the webcam for ~2 s)"
  "$VPY" main.py --camera-diagnostics || warn "no camera delivered frames — fix camera access before launching tracking"
fi

if [[ ${#MISSING_APT[@]} -gt 0 ]]; then
  step "Missing system packages (run these yourself, never with pip)"
  for entry in "${MISSING_APT[@]}"; do apt_hint "$entry"; done
fi

cat <<EOF

AIRDESK is installed in $VENV
    Launch:  ./scripts/run_airdesk_kali.sh
    Tests:   $VPY -m pytest
    Camera:  $VPY main.py --camera-diagnostics
    Full:    $VPY main.py --full-diagnostics --probe-camera
    Docs:    docs/DEPLOYMENT_KALI.md and docs/TESTING_GUIDE.md
EOF
