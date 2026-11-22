#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# AIRDESK — launch on Kali Linux from the project's own virtual environment.
#   ./scripts/run_airdesk_kali.sh
#   ./scripts/run_airdesk_kali.sh --test-mode --source 0
#   ./scripts/run_airdesk_kali.sh --full-diagnostics --probe-camera
#   ./scripts/run_airdesk_kali.sh --no-diagnostics      # skip the pre-flight report

set -euo pipefail

# Resolve the project from this script's location: works from any directory and
# through symlinks (BASH_SOURCE can be relative, so cd first).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

ARGS=()
RUN_DIAGNOSTICS=1
for arg in "$@"; do
  case "$arg" in
    --no-diagnostics) RUN_DIAGNOSTICS=0 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) ARGS+=("$arg") ;;
  esac
done

die() { printf '\nAIRDESK cannot start: %s\n' "$1" >&2; shift; for line in "$@"; do printf '  %s\n' "$line" >&2; done; exit 1; }

if [[ "${EUID}" -eq 0 ]]; then
  die "refusing to run as root." "AIRDESK never needs root; log in as your normal user and run it again."
fi

VPY="$PROJECT_ROOT/.venv/bin/python"
[[ -x "$VPY" ]] || die "no virtual environment found at .venv." \
  "Run ./scripts/bootstrap_kali.sh first (it creates .venv and installs AIRDESK)."

if ! "$VPY" -c "import gestura" >/dev/null 2>&1; then
  die "AIRDESK is not importable from .venv (dependencies incomplete)." \
      "Run ./scripts/bootstrap_kali.sh --recreate"
fi

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  die "no graphical session detected (DISPLAY and WAYLAND_DISPLAY are empty)." \
      "Launch from a terminal inside the desktop session, not over SSH." \
      "If you only want the report, run: $VPY main.py --full-diagnostics"
fi

SESSION_TYPE="${XDG_SESSION_TYPE:-unknown}"
if [[ "$SESSION_TYPE" == "wayland" ]]; then
  printf 'NOTE: Wayland session detected. Mouse/keyboard injection is blocked by the compositor;\n'
  printf '      AIRDESK will track hands and report unsupported actions instead of pretending.\n'
  printf '      For full control, log out and choose an X11 ("Xorg") session.\n\n'
fi

if [[ "$RUN_DIAGNOSTICS" -eq 1 ]]; then
  printf 'AIRDESK pre-flight (airdesk --diagnostics)\n'
  "$VPY" main.py --diagnostics || printf 'WARNING: diagnostics reported problems (see above).\n'
  printf '\n'
fi

exec "$VPY" main.py ${ARGS[@]+"${ARGS[@]}"}
