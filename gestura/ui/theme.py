# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""AIRDESK theme: deep-navy glassmorphism with restrained cyan highlights."""

from __future__ import annotations

BG = "#060a14"
SURFACE = "#0d1626"
SURFACE_2 = "#131f33"
SURFACE_3 = "#1a2b45"
BORDER = "#1e3350"
TEXT = "#e9f2ff"
MUTED = "#8aa3c0"
ACCENT = "#35e0d0"
ACCENT_DIM = "#12564f"
SUCCESS = "#4be0a0"
WARN = "#ffc35c"
DANGER = "#ff5f7a"
DANGER_DIM = "#4a1a25"

STATE_COLORS = {
    "active": SUCCESS,
    "paused": WARN,
    "stopped": MUTED,
    "emergency": DANGER,
    "on": SUCCESS,
    "starting": ACCENT,
    "off": MUTED,
    "lost": WARN,
    "error": DANGER,
}

_STYLESHEET = f"""
* {{ color: {TEXT}; font-size: 10pt; }}
QMainWindow, QWidget#root {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #050912, stop:0.55 #070d1a, stop:1 #0a1524);
}}
QWidget {{ background: transparent; }}
QToolTip {{ background: {SURFACE_3}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; }}

#sidebar {{
    background: #0b1424;
    border-right: 1px solid {BORDER};
}}
#brand {{
    font-size: 18pt; font-weight: 800; letter-spacing: 3.5px; color: #f2fbff;
}}
#brandSub {{ color: {ACCENT}; font-size: 7.6pt; letter-spacing: 1.4px; }}
#navButton {{
    text-align: left; padding: 10px 14px; border: none; border-radius: 9px;
    color: {MUTED}; font-size: 10.5pt;
}}
#navButton:hover {{ background: #102436; color: {TEXT}; }}
#navButton:checked {{
    background: #123047; color: #ffffff;
    border-left: 3px solid {ACCENT};
}}
#privacy {{ color: {MUTED}; font-size: 8.2pt; }}

#topbar {{
    background: #080e1a;
    border-bottom: 1px solid {BORDER};
}}
#pageTitle {{ font-size: 15pt; font-weight: 650; letter-spacing: 0.4px; }}
#tagline {{ color: {MUTED}; font-size: 8.2pt; letter-spacing: 2px; }}

QFrame#card {{
    background: #101c2e;
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
#cardTitle {{ color: #7f9cbd; font-size: 8.2pt; font-weight: 700; letter-spacing: 1.6px; }}
#bigValue {{ font-size: 18pt; font-weight: 650; }}
#value {{ font-size: 11pt; }}
#muted {{ color: {MUTED}; }}
#hint {{ color: {MUTED}; font-size: 9pt; }}
#modeBadge {{
    color: {ACCENT}; font-size: 9pt; font-weight: 700; letter-spacing: 1.4px;
}}

QPushButton {{
    background: #1a2b45; border: 1px solid {BORDER}; border-radius: 9px;
    padding: 8px 16px; font-weight: 550;
}}
QPushButton:hover {{ background: #223857; border-color: #2c4a6d; }}
QPushButton:pressed {{ background: {SURFACE_2}; }}
QPushButton:disabled {{ color: #596a80; }}
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2fd9c9, stop:1 #3fb6ff);
    color: #03121a; border: none; font-weight: 800;
}}
QPushButton#primary:hover {{ background: #5ce6d9; }}
QPushButton#danger {{
    background: {DANGER}; color: white; border: none; font-weight: 800;
    padding: 10px 18px; letter-spacing: 0.6px;
}}
QPushButton#danger:hover {{ background: #ff7d93; }}
QPushButton#ghost {{ background: transparent; border: 1px solid {BORDER}; }}

#chip {{
    background: #131f33; border: 1px solid {BORDER}; border-radius: 13px;
    padding: 4px 12px; font-size: 9pt;
}}
#banner {{ background: #12403a; border: 1px solid {ACCENT_DIM}; border-radius: 8px; padding: 8px 12px; }}
#bannerDanger {{ background: {DANGER_DIM}; border: 1px solid {DANGER}; border-radius: 8px; padding: 10px 12px; }}

QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 12px; top: -1px; background: #0d1626; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 7px 9px; font-size: 9pt; border: none; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: 10px; margin-top: 14px; padding: 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {MUTED}; }}

QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {{
    background: #131f33; border: 1px solid {BORDER}; border-radius: 7px;
    padding: 5px 8px; min-height: 20px;
}}
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {{ border-color: {ACCENT}; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: 22px; border: none; background: {SURFACE_3};
}}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; border-top-right-radius: 6px; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; border-bottom-right-radius: 6px; }}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{ background: #2a4364; }}
QAbstractSpinBox::up-arrow {{ image: url(@ASSETS@/ui/arrow_up.svg); width: 10px; height: 6px; }}
QAbstractSpinBox::down-arrow {{ image: url(@ASSETS@/ui/arrow_down.svg); width: 10px; height: 6px; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url(@ASSETS@/ui/arrow_down.svg); width: 10px; height: 6px; }}
QComboBox QAbstractItemView {{ background: {SURFACE_2}; selection-background-color: {SURFACE_3}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {BORDER}; background: {SURFACE_2}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url(@ASSETS@/ui/check.svg); }}
QCheckBox {{ spacing: 8px; }}
QListWidget {{ background: #131f33; border: 1px solid {BORDER}; border-radius: 9px; padding: 4px; }}
QListWidget::item {{ padding: 5px 6px; border-radius: 5px; }}
QListWidget::item:selected {{ background: #1b4a52; color: #ffffff; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_3}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QSlider::groove:horizontal {{ height: 4px; background: {SURFACE_3}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT}; width: 14px; margin: -6px 0; border-radius: 7px; }}

#keyButton {{
    background: #131f33; border: 1px solid {BORDER}; border-radius: 9px;
    font-size: 13pt; font-weight: 500; padding: 0;
}}
#keyButton:hover {{ background: {SURFACE_3}; border-color: {ACCENT}; }}
#keyButton:pressed {{ background: {ACCENT}; color: #04121a; }}
#keyButton:checked {{ background: {ACCENT_DIM}; border-color: {ACCENT}; }}
QWidget#keyboardWindow {{
    background: #0d1626; border: 1px solid {BORDER}; border-radius: 14px;
}}
"""


def stylesheet() -> str:
    """The stylesheet with asset paths resolved (Qt needs forward slashes)."""
    from ..vision.models import assets_dir

    return _STYLESHEET.replace("@ASSETS@", assets_dir().as_posix())
