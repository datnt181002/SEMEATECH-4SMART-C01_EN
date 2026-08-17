"""Raw serial monitor tab."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.communication.serial_worker import parse_hex_input
from app.protocol.frames import hex_bytes


class SerialMonitor(QWidget):
    raw_send_requested = Signal(bytes)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.clear_button = QPushButton("Clear")
        self.copy_button = QPushButton("Copy")
        self.save_button = QPushButton("Save Log")
        self.autoscroll_check = QCheckBox("Auto Scroll")
        self.autoscroll_check.setChecked(True)
        toolbar.addWidget(self.clear_button)
        toolbar.addWidget(self.copy_button)
        toolbar.addWidget(self.save_button)
        toolbar.addStretch()
        toolbar.addWidget(self.autoscroll_check)
        root.addLayout(toolbar)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QTextEdit.NoWrap)
        root.addWidget(self.text, 1)

        raw = QHBoxLayout()
        self.raw_input = QLineEdit()
        self.raw_input.setPlaceholderText("AA 01 01 C1 E0 EE")
        self.raw_send_button = QPushButton("Send Raw HEX")
        self.raw_send_button.setToolTip("Bypasses normal command validation. Bytes are sent exactly as entered.")
        raw.addWidget(self.raw_input, 1)
        raw.addWidget(self.raw_send_button)
        root.addLayout(raw)

        self.clear_button.clicked.connect(self.text.clear)
        self.copy_button.clicked.connect(self.text.copy)
        self.save_button.clicked.connect(self._save)
        self.raw_send_button.clicked.connect(self._send_raw)

    def append_event(self, direction: str, payload: bytes, status: str, message: str = "") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        rendered = hex_bytes(payload) if payload else ""
        color = {
            "tx": "#1d4ed8",
            "rx_valid": "#047857",
            "crc_error": "#b91c1c",
            "timeout": "#b45309",
            "malformed": "#be123c",
            "garbage": "#6b7280",
            "simulation": "#7c3aed",
        }.get(status, "#111827")
        suffix = f"  {message}" if message else ""
        self.text.append(f'<span style="color:{color}">{timestamp}  {direction:<2}  {rendered}{suffix}</span>')
        if self.autoscroll_check.isChecked():
            self.text.moveCursor(QTextCursor.End)

    def _send_raw(self) -> None:
        try:
            payload = parse_hex_input(self.raw_input.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid HEX", str(exc))
            return
        self.raw_send_requested.emit(payload)

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Serial Monitor Log", "serial_monitor.txt", "Text files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.text.toPlainText())
