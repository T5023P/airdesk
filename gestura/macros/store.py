# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""Macro persistence: one JSON file, atomic writes, corrupt file quarantined."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from pydantic import ValidationError

from ..services.configuration_service import config_dir
from .model import MacroBook

log = logging.getLogger(__name__)


def default_macro_path() -> Path:
    return config_dir() / "macros.json"


class MacroStore:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else default_macro_path()
        self.error = ""

    def load(self) -> MacroBook:
        if not self.path.exists():
            return MacroBook()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return MacroBook.model_validate(data)
        except (OSError, ValueError, ValidationError) as exc:
            backup = self.path.with_suffix(f".invalid-{int(time.time())}.json")
            try:
                self.path.replace(backup)
            except OSError:
                pass
            self.error = f"Macro file was invalid and has been reset (backup: {backup.name}): {exc}"
            log.warning(self.error)
            return MacroBook()

    def save(self, book: MacroBook) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(book.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
