# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Locations of the bundled MediaPipe model files."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

HAND_MODEL = "hand_landmarker.task"
FACE_MODEL = "face_landmarker.task"

# SHA-256 of the bundled float16 models (downloaded 2026-11-06 from
# storage.googleapis.com/mediapipe-models/.../float16/latest/).
MODEL_SHA256 = {
    HAND_MODEL: "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1",
    FACE_MODEL: "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
}

MODEL_URLS = {
    HAND_MODEL: "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task",
    FACE_MODEL: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
}


def assets_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)  # PyInstaller one-file / one-dir bundle
    if base:
        return Path(base) / "gestura" / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


def model_dir() -> Path:
    """Platform-independent model directory (bundle-aware, never absolute)."""
    return assets_dir() / "models"


def model_path(name: str) -> Path:
    path = model_dir() / name
    if not path.is_file():
        raise FileNotFoundError(
            f"MediaPipe model {name!r} not found at {path}. "
            "Run `python scripts/download_models.py` to fetch it."
        )
    return path


@dataclass(slots=True)
class ModelCheck:
    """Result of verifying one bundled model file before startup."""

    name: str
    path: Path
    present: bool
    size: int = 0
    sha256: str = ""
    hash_ok: bool | None = None
    detail: str = ""

    @property
    def usable(self) -> bool:
        return self.present and self.size > 0 and self.hash_ok is not False

    def summary(self) -> str:
        if not self.present:
            return f"{self.name}: MISSING at {self.path}"
        state = "ok" if self.hash_ok else ("unverified" if self.hash_ok is None else "CHECKSUM MISMATCH")
        return f"{self.name}: {self.size / 1_048_576:.1f} MiB, {state}"


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_model(name: str, *, check_hash: bool = True) -> ModelCheck:
    """Check one model without raising: diagnostics must always finish."""
    path = model_dir() / name
    check = ModelCheck(name=name, path=path, present=path.is_file())
    if not check.present:
        check.detail = "run `python scripts/download_models.py` (source documented in UPSTREAM.md)"
        return check
    try:
        check.size = path.stat().st_size
        if check_hash:
            expected = MODEL_SHA256.get(name)
            check.sha256 = sha256_file(path)
            if expected:
                check.hash_ok = check.sha256 == expected
                if not check.hash_ok:
                    check.detail = ("checksum differs from the pinned model: re-download it with "
                                    "`python scripts/download_models.py --force`")
        else:
            check.hash_ok = None
    except OSError as exc:  # pragma: no cover - unreadable file
        check.detail = f"unreadable: {exc}"
        check.hash_ok = False
    return check


def verify_models(*, check_hash: bool = True) -> list[ModelCheck]:
    return [verify_model(HAND_MODEL, check_hash=check_hash),
            verify_model(FACE_MODEL, check_hash=check_hash)]


def models_ready(*, check_hash: bool = True) -> bool:
    """True when every bundled model exists and matches its pinned checksum."""
    return all(check.usable for check in verify_models(check_hash=check_hash))
