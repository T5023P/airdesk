# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Gestura contributors
#
# This file is part of Gestura, free and open-source software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Gestura is distributed
# WITHOUT ANY WARRANTY; see the LICENSE file at the project root for details.
"""AIR MACROS editor: create, edit, reorder, enable, test and save macros."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...macros.model import (
    ALLOWED_APPS,
    ALLOWED_DIRECTIONS,
    ALLOWED_MODES,
    ALLOWED_SHORTCUTS,
    ALLOWED_TRIGGERS,
    ALLOWED_VOLUME,
    Macro,
    MacroAction,
    MacroBook,
    new_action,
    new_macro,
)
from ..widgets.common import Card, label

ACTION_TYPES: list[tuple[str, str]] = [
    ("open_app", "Open an application"),
    ("shortcut", "Press a keyboard shortcut"),
    ("set_mode", "Change application mode"),
    ("air_command", "Run an AIR COMMAND"),
    ("keyboard", "Show / hide the virtual keyboard"),
    ("volume", "Change the volume"),
    ("presentation", "Navigate presentation slides"),
    ("wait", "Wait"),
]

TARGETS: dict[str, dict[str, str]] = {
    "open_app": ALLOWED_APPS,
    "shortcut": ALLOWED_SHORTCUTS,
    "set_mode": ALLOWED_MODES,
    "volume": ALLOWED_VOLUME,
    "presentation": ALLOWED_DIRECTIONS,
}


def trigger_label(name: str) -> str:
    if name.startswith("chord."):
        return "Chord · " + name.removeprefix("chord.").replace("_", " ").replace("+", " + ")
    return name.split(".")[-1].replace("_", " ").capitalize()


class MacrosPage(QWidget):
    def __init__(self, app, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self._draft: Macro | None = None
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(14)
        header = QHBoxLayout()
        header.addWidget(label(
            "Bind a safe, multi-step macro to a gesture. Every step is allow-listed — "
            "no shell commands, no file system writes.", "hint", wrap=True), 1)
        self.status = label("", "hint", wrap=True)
        root.addLayout(header)
        root.addWidget(self.status)

        body = QHBoxLayout()
        body.setSpacing(14)

        left = Card("Macros")
        left.setFixedWidth(320)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._selected)
        left.body.addWidget(self.list, 1)
        row = QHBoxLayout()
        for text, slot in (("New", self._new), ("Delete", self._delete)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        left.body.addLayout(row)
        body.addWidget(left)

        right = Card("Macro editor")
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._apply_form)
        self.gesture_combo = QComboBox()
        for trigger in ALLOWED_TRIGGERS:
            self.gesture_combo.addItem(trigger_label(trigger), trigger)
        self.gesture_combo.currentIndexChanged.connect(self._apply_form)
        self.enabled_box = QCheckBox("Enabled")
        self.enabled_box.toggled.connect(self._apply_form)
        self.confirm_box = QCheckBox("Ask for confirmation before running from a gesture")
        self.confirm_box.toggled.connect(self._apply_form)

        form_row = QHBoxLayout()
        form_row.addWidget(label("Name", "hint"))
        form_row.addWidget(self.name_edit, 1)
        right.body.addLayout(form_row)
        gesture_row = QHBoxLayout()
        gesture_row.addWidget(label("Gesture", "hint"))
        gesture_row.addWidget(self.gesture_combo, 1)
        right.body.addLayout(gesture_row)
        checks = QHBoxLayout()
        checks.addWidget(self.enabled_box)
        checks.addWidget(self.confirm_box)
        checks.addStretch(1)
        right.body.addLayout(checks)

        right.body.addWidget(label("Steps", "cardTitle"))
        self.steps = QListWidget()
        self.steps.setMinimumHeight(160)
        self.steps.currentRowChanged.connect(self._step_selected)
        right.body.addWidget(self.steps, 1)

        step_row = QHBoxLayout()
        self.type_combo = QComboBox()
        for key, text in ACTION_TYPES:
            self.type_combo.addItem(text, key)
        self.type_combo.currentIndexChanged.connect(self._type_changed)
        self.target_combo = QComboBox()
        self.target_combo.setMinimumWidth(180)
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 10000)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setValue(150)
        add = QPushButton("Add step")
        add.clicked.connect(self._add_step)
        step_row.addWidget(self.type_combo)
        step_row.addWidget(self.target_combo, 1)
        step_row.addWidget(self.delay_spin)
        step_row.addWidget(add)
        right.body.addLayout(step_row)

        edit_row = QHBoxLayout()
        for text, slot in (("Move up", lambda: self._move(-1)), ("Move down", lambda: self._move(1)),
                           ("Apply delay", self._apply_delay), ("Remove step", self._remove_step)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            edit_row.addWidget(b)
        edit_row.addStretch(1)
        right.body.addLayout(edit_row)

        actions = QHBoxLayout()
        self.test_btn = QPushButton("Test macro")
        self.test_btn.clicked.connect(self._test)
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        actions.addWidget(self.test_btn)
        actions.addStretch(1)
        actions.addWidget(save)
        right.body.addLayout(actions)
        body.addWidget(right, 1)
        root.addLayout(body, 1)

        self._type_changed(0)
        self._reload_list()

    # ------------------------------------------------------------------ list
    def _reload_list(self) -> None:
        current_id = self._draft.id if self._draft else None
        self.list.blockSignals(True)
        self.list.clear()
        for macro in self.app.macro_book.macros:
            item = QListWidgetItem(("● " if macro.enabled else "○ ") + macro.name)
            item.setData(Qt.ItemDataRole.UserRole, macro.id)
            self.list.addItem(item)
        self.list.blockSignals(False)
        row = next((i for i, m in enumerate(self.app.macro_book.macros) if m.id == current_id), 0)
        if self.app.macro_book.macros:
            self.list.setCurrentRow(row)
        else:
            self._set_draft(None)

    def _selected(self, row: int) -> None:
        if self._loading:
            return
        macros = self.app.macro_book.macros
        self._set_draft(macros[row] if 0 <= row < len(macros) else None)

    def _set_draft(self, macro: Macro | None) -> None:
        self._loading = True
        try:
            self._draft = macro.model_copy(deep=True) if macro else None
            enabled = macro is not None
            for w in (self.name_edit, self.gesture_combo, self.enabled_box, self.confirm_box,
                      self.steps, self.type_combo, self.target_combo, self.delay_spin,
                      self.test_btn):
                w.setEnabled(enabled)
            if macro:
                self.name_edit.setText(macro.name)
                self.gesture_combo.setCurrentIndex(max(0, self.gesture_combo.findData(macro.gesture)))
                self.enabled_box.setChecked(macro.enabled)
                self.confirm_box.setChecked(macro.confirm)
            else:
                self.name_edit.clear()
                self.steps.clear()
        finally:
            self._loading = False
        self._refresh_steps()

    # ----------------------------------------------------------------- steps
    def _refresh_steps(self) -> None:
        self.steps.blockSignals(True)
        self.steps.clear()
        if self._draft is not None:
            for action in self._draft.actions:
                self.steps.addItem(f"{action.describe()}  ·  {action.delay_ms} ms")
        self.steps.blockSignals(False)

    def _type_changed(self, _index: int) -> None:
        kind = self.type_combo.currentData()
        self.target_combo.clear()
        for key, text in TARGETS.get(kind, {}).items():
            self.target_combo.addItem(text, key)
        hint_less = kind in ("keyboard", "wait", "air_command")
        self.target_combo.setEnabled(not hint_less or kind == "air_command")
        if kind == "air_command":
            from ...core.air_commands import AIR_COMMANDS

            for command in AIR_COMMANDS:
                self.target_combo.addItem(command.label, command.id)

    def _add_step(self) -> None:
        if self._draft is None:
            return
        kind = self.type_combo.currentData()
        target = self.target_combo.currentData() or ""
        delay = self.delay_spin.value()
        try:
            action = new_action(kind, str(target), delay)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self.status.setText(f"Not added: {exc}")
            return
        self._draft.actions.append(action)
        self._refresh_steps()
        self.steps.setCurrentRow(len(self._draft.actions) - 1)
        self.status.setText("Step added (press Save to keep it).")

    def _step_selected(self, row: int) -> None:
        if self._draft and 0 <= row < len(self._draft.actions):
            self.delay_spin.setValue(self._draft.actions[row].delay_ms)

    def _move(self, delta: int) -> None:
        row = self.steps.currentRow()
        if self._draft is None or row < 0:
            return
        target = row + delta
        if not 0 <= target < len(self._draft.actions):
            return
        actions = self._draft.actions
        actions[row], actions[target] = actions[target], actions[row]
        self._refresh_steps()
        self.steps.setCurrentRow(target)

    def _remove_step(self) -> None:
        row = self.steps.currentRow()
        if self._draft is None or row < 0:
            return
        del self._draft.actions[row]
        self._refresh_steps()

    def _apply_delay(self) -> None:
        row = self.steps.currentRow()
        if self._draft is None or row < 0:
            return
        self._draft.actions[row] = self._draft.actions[row].model_copy(
            update={"delay_ms": self.delay_spin.value()})
        self._refresh_steps()

    # ------------------------------------------------------------------ form
    def _apply_form(self, *_args) -> None:
        if self._loading or self._draft is None:
            return
        self._draft = self._draft.model_copy(update={
            "name": self.name_edit.text().strip() or "Untitled macro",
            "gesture": self.gesture_combo.currentData(),
            "enabled": self.enabled_box.isChecked(),
            "confirm": self.confirm_box.isChecked(),
        })

    def _new(self) -> None:
        macro = new_macro(f"Macro {len(self.app.macro_book.macros) + 1}")
        book = MacroBook(version=self.app.macro_book.version,
                         macros=[*self.app.macro_book.macros, macro])
        self.app.save_macros(book)
        self._draft = macro
        self._reload_list()

    def _delete(self) -> None:
        macro = self._draft
        if macro is None:
            return
        if QMessageBox.question(self, "Delete macro", f"Delete “{macro.name}”?") \
                != QMessageBox.StandardButton.Yes:
            return
        book = MacroBook(version=self.app.macro_book.version,
                         macros=[m for m in self.app.macro_book.macros if m.id != macro.id])
        self.app.save_macros(book)
        self._draft = None
        self._reload_list()
        self.status.setText("Macro deleted.")

    def _validated(self) -> Macro | None:
        self._apply_form()
        if self._draft is None:
            return None
        try:
            return Macro.model_validate(self._draft.model_dump())
        except Exception as exc:  # noqa: BLE001 - shown in the page
            self.status.setText(f"Invalid macro: {exc}")
            return None

    def _save(self) -> None:
        macro = self._validated()
        if macro is None:
            return
        macros = [m for m in self.app.macro_book.macros if m.id != macro.id] + [macro]
        macros.sort(key=lambda m: (m.name.lower()))
        self.app.save_macros(MacroBook(version=self.app.macro_book.version, macros=macros))
        self._draft = macro
        self._reload_list()
        self.status.setText(f"Saved “{macro.name}”.")

    def _test(self) -> None:
        macro = self._validated()
        if macro is None:
            return
        if macro.confirm and QMessageBox.question(
                self, "Run macro", f"Run “{macro.name}” now?") != QMessageBox.StandardButton.Yes:
            return
        result = self.app.run_macro(macro, confirmed=True)
        self.status.setText(("OK — " if result.ok else "Stopped — ") + result.summary)
