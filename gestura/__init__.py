# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""AIRDESK — hands-free desktop control, derived from Gestura.

The Python package is still called ``gestura`` on purpose: it keeps every
existing import, test and packaging path working, and it keeps upstream
attribution visible in every traceback.
"""

__version__ = "0.4.0"

APP_NAME = "AIRDESK"
APP_TAGLINE = "YOUR HANDS. YOUR COMPUTER. NO TOUCH REQUIRED."
APP_DESCRIPTION = "Offline, webcam-based hands-free computer control."

#: Upstream project this application is derived from (GPL-3.0-or-later).
UPSTREAM_NAME = "Gestura"
UPSTREAM_URL = "https://github.com/Raphzaf/gestura"
UPSTREAM_VERSION = "0.3.0"
UPSTREAM_AUTHOR = "Raphzaf and Gestura contributors"

#: Kept for existing links/UI that point at the source repository.
SOURCE_URL = UPSTREAM_URL

__all__ = [
    "__version__",
    "APP_NAME",
    "APP_TAGLINE",
    "APP_DESCRIPTION",
    "UPSTREAM_NAME",
    "UPSTREAM_URL",
    "UPSTREAM_VERSION",
    "UPSTREAM_AUTHOR",
    "SOURCE_URL",
]
