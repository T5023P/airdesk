#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# Build a clean AIRDESK source archive for the Windows → Kali transfer.
#   ./scripts/make_source_archive.sh                 # writes dist/airdesk-src-<date>.tar.gz
#   ./scripts/make_source_archive.sh /tmp/out.tar.gz
#
# Included: source, tests, docs, website, packaging, configuration, the bundled
# MediaPipe models, LICENSE, UPSTREAM.md, README, CHANGELOG.
# Excluded: any virtual environment, __pycache__, pytest/mypy caches, build
# artifacts, logs, local settings, .env files, screenshots and smoke captures.
# A Windows .venv is never portable to Linux, so it must not travel.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

STAMP="$(date +%Y%m%d-%H%M)"
TARGET="${1:-$PROJECT_ROOT/dist/airdesk-src-$STAMP.tar.gz}"
mkdir -p "$(dirname "$TARGET")"

if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  printf 'NOTE: the working tree has uncommitted changes; the archive contains the working tree as-is.\n'
  printf '      Bump the CHANGELOG and commit before shipping if this is a release.\n\n'
fi

tar --create --gzip --file "$TARGET" \
  --exclude='.venv' --exclude='venv' --exclude='env' \
  --exclude='__pycache__' --exclude='*.py[cod]' \
  --exclude='.pytest_cache' --exclude='.mypy_cache' --exclude='.ruff_cache' \
  --exclude='.git' --exclude='.freebuff' --exclude='.idea' --exclude='.vscode' \
  --exclude='build' --exclude='dist' --exclude='*.egg-info' \
  --exclude='store/out' --exclude='installer/Output' \
  --exclude='*.log' --exclude='*.tmp' --exclude='.env' --exclude='.env.*' \
  --exclude='*.pfx' --exclude='*.p12' \
  --exclude='airdesk-*.png' --exclude='smoke*.png' --exclude='*.mp4' \
  --exclude='_attic' \
  .

# Verify the essentials preserved attribution + licence + models.
# Capture the listing once: piping tar into `grep -q` makes grep exit early and
# tar die on SIGPIPE, which `set -o pipefail` would turn into a false failure.
LISTING="$(tar --list --file "$TARGET")" || { printf 'ERROR: cannot read %s\n' "$TARGET" >&2; exit 1; }
for required in LICENSE UPSTREAM.md README.md pyproject.toml requirements.txt \
                gestura/assets/models/hand_landmarker.task \
                gestura/assets/models/face_landmarker.task; do
  if ! grep -qx "./$required" <<< "$LISTING"; then
    printf 'ERROR: %s is missing from the archive\n' "$required" >&2
    exit 1
  fi
done
if grep -qE '^\./(\.venv|venv|env)/' <<< "$LISTING"; then
  printf 'ERROR: a virtual environment leaked into the archive\n' >&2
  exit 1
fi

SIZE="$(du -h "$TARGET" | cut -f1)"
printf 'Wrote %s (%s)\n' "$TARGET" "$SIZE"
printf 'On Kali:\n'
printf '  tar -xzf %s -C ~/airdesk-src && cd ~/airdesk-src\n' "$(basename "$TARGET")"
printf '  ./scripts/bootstrap_kali.sh --probe-camera\n'
