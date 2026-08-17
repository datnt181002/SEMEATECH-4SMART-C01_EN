"""Worker object that owns the serial port and runs in a Qt thread."""

from __future__ import annotations

import time
from dataclasses import asdict

from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.protocol.frames import Frame, FrameError, hex_bytes
from app.protocol.models import ErrorCounters
from app.protocol.parser import FrameParser


class SerialWorker(QObject):
    opened = Signal(str)
    closed = Signal()
    connection_lost = Signal(str)
    frame_received = Signal(object)
    serial_event = Signal(str, bytes, str, str)
    counters_changed = Signal(dict)
    timeout = Signal(int)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._serial = None
        self._parser = FrameParser()
        self._busy = False
        self._counters = ErrorCounters()

    @Slot(str, int, int)
    def open_port(self, port: str, baud_rate: int, timeout_ms: int) -> None:
        try:
            import serial

            self._serial = serial.Serial(
                port=port,
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=max(timeout_ms / 1000.0 / 10.0, 0.02),
                write_timeout=1.0,
            )
            self._parser.reset()
            self.opened.emit(port)
        except Exception as exc:  # pragma: no cover - hardware dependent
            self._serial = None
            self.error.emit(f"Could not open {port}: {exc}")

    @Slot()
    def close_port(self) -> None:
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
        finally:
            self._serial = None
            self._busy = False
            self.closed.emit()

    @Slot(bytes, int, int, int)
    def transact(self, request: bytes, expected_command: int, timeout_ms: int, retries: int) -> None:
        if self._busy:
            self.error.emit("A serial transaction is already active")
            return
        if not self._serial or not self._serial.is_open:
            self.error.emit("Serial port is not open")
            return

        self._busy = True
        try:
            for attempt in range(retries + 1):
                self._parser.reset()
                self._write(request)
                frame = self._read_until_expected(expected_command, timeout_ms)
                if frame is not None:
                    self._counters.successful_frames += 1
                    self._emit_counters()
                    self.frame_received.emit(frame)
                    return
                self._counters.timeouts += 1
                self._emit_counters()
                self.timeout.emit(expected_command)
                if attempt < retries:
                    QThread.msleep(30)
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.connection_lost.emit(str(exc))
            self.close_port()
        finally:
            self._busy = False

    @Slot(bytes, int)
    def send_raw(self, request: bytes, listen_ms: int) -> None:
        if self._busy:
            self.error.emit("A serial transaction is already active")
            return
        if not self._serial or not self._serial.is_open:
            self.error.emit("Serial port is not open")
            return
        self._busy = True
        try:
            self._parser.reset()
            self._write(request)
            self._read_raw_window(listen_ms)
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.connection_lost.emit(str(exc))
            self.close_port()
        finally:
            self._busy = False

    def _write(self, request: bytes) -> None:
        self._serial.write(request)
        self._serial.flush()
        self.serial_event.emit("TX", request, "tx", "")

    def _read_until_expected(self, expected_command: int, timeout_ms: int) -> Frame | None:
        deadline = time.monotonic() + timeout_ms / 1000.0
        while time.monotonic() < deadline:
            waiting = getattr(self._serial, "in_waiting", 0)
            chunk = self._serial.read(waiting or 1)
            if chunk:
                for event in self._parser.feed(chunk):
                    if event.ok and event.frame:
                        status = "rx_valid"
                        self.serial_event.emit("RX", event.raw, status, "")
                        if int(event.frame.command) == expected_command:
                            return event.frame
                    elif event.error == FrameError.CRC:
                        self._counters.crc_errors += 1
                        self.serial_event.emit("RX", event.raw, "crc_error", event.message)
                    elif event.error == FrameError.MALFORMED:
                        self._counters.malformed_frames += 1
                        self.serial_event.emit("RX", event.raw, "malformed", event.message)
                    elif event.raw:
                        self.serial_event.emit("RX", event.raw, "garbage", event.message)
                    self._emit_counters()
            QThread.msleep(2)
        self.serial_event.emit("RX", b"", "timeout", f"Timeout waiting for command 0x{expected_command:02X}")
        return None

    def _read_raw_window(self, listen_ms: int) -> None:
        deadline = time.monotonic() + max(listen_ms, 50) / 1000.0
        saw_any_frame = False
        while time.monotonic() < deadline:
            waiting = getattr(self._serial, "in_waiting", 0)
            chunk = self._serial.read(waiting or 1)
            if chunk:
                for event in self._parser.feed(chunk):
                    if event.ok and event.frame:
                        saw_any_frame = True
                        self._counters.successful_frames += 1
                        self.serial_event.emit("RX", event.raw, "rx_valid", "raw response")
                        self.frame_received.emit(event.frame)
                    elif event.error == FrameError.CRC:
                        saw_any_frame = True
                        self._counters.crc_errors += 1
                        self.serial_event.emit("RX", event.raw, "crc_error", event.message)
                    elif event.error == FrameError.MALFORMED:
                        saw_any_frame = True
                        self._counters.malformed_frames += 1
                        self.serial_event.emit("RX", event.raw, "malformed", event.message)
                    elif event.raw:
                        self.serial_event.emit("RX", event.raw, "garbage", event.message)
                    self._emit_counters()
            QThread.msleep(2)
        if not saw_any_frame and not self._parser.buffered:
            self.serial_event.emit("RX", b"", "timeout", "No raw response received")

    def _emit_counters(self) -> None:
        self.counters_changed.emit(asdict(self._counters))


def list_serial_ports() -> list[str]:
    try:
        from serial.tools import list_ports

        return [port.device for port in list_ports.comports()]
    except Exception:
        return []


def parse_hex_input(text: str) -> bytes:
    cleaned = text.replace(",", " ").replace(";", " ")
    parts = [part for part in cleaned.split() if part]
    if not parts:
        raise ValueError("Enter at least one hex byte")
    values = []
    for part in parts:
        if part.lower().startswith("0x"):
            part = part[2:]
        if len(part) > 2:
            raise ValueError(f"Invalid byte '{part}'")
        value = int(part, 16)
        if not 0 <= value <= 0xFF:
            raise ValueError(f"Byte out of range '{part}'")
        values.append(value)
    return bytes(values)
