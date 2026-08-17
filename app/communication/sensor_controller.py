"""Qt-facing sensor controller with hardware and simulation modes."""

from __future__ import annotations

import math
import random
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QThread, QTimer, Signal

from app.logging.data_logger import DataLogger
from app.protocol import commands
from app.protocol.commands import AckStatus, Command
from app.protocol.decoder import ProtocolError, decode_ack, decode_gas_reading, decode_module_info
from app.protocol.frames import Frame, hex_bytes
from app.protocol.models import CommandAck, ErrorCounters, GasReading, ModuleInfo

from .serial_worker import SerialWorker, list_serial_ports


class SensorController(QObject):
    connected = Signal(str)
    disconnected = Signal()
    connection_lost = Signal(str)
    module_info_received = Signal(object)
    reading_received = Signal(object)
    ack_received = Signal(object)
    error = Signal(str)
    status = Signal(str)
    serial_event = Signal(str, bytes, str, str)
    counters_changed = Signal(dict)
    logging_changed = Signal(bool, str, int)
    scan_started = Signal(int, int)
    scan_progress = Signal(int)
    scan_found = Signal(object)
    scan_finished = Signal(list)

    request_open = Signal(str, int, int)
    request_close = Signal()
    request_transaction = Signal(bytes, int, int, int)
    request_raw = Signal(bytes, int)

    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("SemeaTech", "4SMART-C01 Sensor Utility")
        self.address = int(self.settings.value("serial/address", 1))
        self.baud_rate = int(self.settings.value("serial/baud_rate", 9600))
        self.timeout_ms = int(self.settings.value("serial/timeout_ms", 500))
        self.retries = int(self.settings.value("serial/retries", 2))
        self.interval_ms = int(self.settings.value("acquisition/interval_ms", 1000))
        self.history_seconds = int(self.settings.value("graph/history_seconds", 300))
        self.log_directory = str(self.settings.value("logging/default_dir", str(Path.home() / "Documents")))

        self.module_info: ModuleInfo | None = None
        self.connected_port = ""
        self.simulation = False
        self._pending_command: Command | None = None
        self._polling_before_service = False
        self._expected_calibration_gas: int | None = None
        self._expected_new_address: int | None = None
        self._scan_active = False
        self._scan_queue: list[int] = []
        self._scan_results: list[ModuleInfo] = []
        self._address_before_scan = self.address
        self._polling_before_scan = False
        self._rng = random.Random()
        self._simulation_t = 0.0

        self._thread = QThread(self)
        self._worker = SerialWorker()
        self._worker.moveToThread(self._thread)
        self.request_open.connect(self._worker.open_port)
        self.request_close.connect(self._worker.close_port)
        self.request_transaction.connect(self._worker.transact)
        self.request_raw.connect(self._worker.send_raw)
        self._worker.opened.connect(self._on_opened)
        self._worker.closed.connect(self._on_closed)
        self._worker.connection_lost.connect(self._on_connection_lost)
        self._worker.frame_received.connect(self._on_frame)
        self._worker.serial_event.connect(self.serial_event)
        self._worker.counters_changed.connect(self.counters_changed)
        self._worker.timeout.connect(self._on_timeout)
        self._worker.error.connect(self.error)
        self._thread.start()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self.poll_concentration)
        self._simulation_timer = QTimer(self)
        self._simulation_timer.timeout.connect(self._emit_simulated_reading)
        self.logger = DataLogger()

    @staticmethod
    def available_ports() -> list[str]:
        return list_serial_ports()

    def shutdown(self) -> None:
        self.stop_acquisition()
        if self.logger.active:
            self.stop_logging()
        self.disconnect_sensor()
        self._thread.quit()
        self._thread.wait(1500)

    def connect_sensor(self, port: str, *, simulation: bool = False) -> None:
        self.simulation = simulation
        if simulation:
            self.connected_port = "SIMULATION"
            self.module_info = ModuleInfo(
                address=self.address,
                sensor_type_code=0x0F,
                sensor_type_name="PH3",
                measurement_range=20,
                calibration_concentration=5,
                high_alarm=2,
                low_alarm=1,
                unit_code=0x02,
                unit_name="ppm",
            )
            self.connected.emit(self.connected_port)
            self.module_info_received.emit(self.module_info)
            self.status.emit("SIMULATION connected")
            return
        self.request_open.emit(port, self.baud_rate, self.timeout_ms)

    def disconnect_sensor(self) -> None:
        self.stop_acquisition()
        if self.simulation:
            self.simulation = False
            self.connected_port = ""
            self.disconnected.emit()
            return
        self.request_close.emit()

    def read_module_info(self) -> None:
        if self.simulation:
            if self.module_info:
                self.module_info_received.emit(self.module_info)
            return
        self._send(commands.read_info(self.address), Command.READ_INFO)

    def poll_concentration(self) -> None:
        if self.simulation:
            self._emit_simulated_reading()
            return
        self._send(commands.read_concentration(self.address), Command.READ_CONCENTRATION)

    def zero(self) -> None:
        self._service_transaction(commands.zero(self.address), Command.ZERO, "Zero-setting in progress...")

    def calibrate(self) -> None:
        self._service_transaction(commands.calibrate(self.address), Command.CALIBRATE, "Calibration in progress. Waiting for module result.")

    def change_address(self, new_address: int) -> None:
        self._expected_new_address = new_address & 0xFF
        self._service_transaction(commands.change_address(new_address), Command.CHANGE_ADDRESS, "Changing module address...")

    def set_calibration_gas(self, concentration: int) -> None:
        self._expected_calibration_gas = concentration
        self._service_transaction(commands.set_calibration_gas(self.address, concentration), Command.SET_CAL_GAS, "Setting calibration gas concentration...")

    def scan_addresses(self, start_address: int = 0, end_address: int = 255) -> None:
        if start_address > end_address:
            start_address, end_address = end_address, start_address
        if self.simulation:
            if self.module_info:
                self.scan_started.emit(start_address, end_address)
                self.scan_found.emit(self.module_info)
                self.scan_finished.emit([self.module_info])
            return
        if self._scan_active:
            self.error.emit("Address scan is already active")
            return
        if self._pending_command is not None:
            self.error.emit("Wait for the active transaction to finish before scanning")
            return
        self._polling_before_scan = self.acquisition_active
        self.stop_acquisition()
        self._scan_active = True
        self._scan_queue = list(range(start_address & 0xFF, (end_address & 0xFF) + 1))
        self._scan_results = []
        self._address_before_scan = self.address
        self.scan_started.emit(start_address & 0xFF, end_address & 0xFF)
        self.status.emit(f"Scanning addresses 0x{start_address & 0xFF:02X}-0x{end_address & 0xFF:02X}...")
        QTimer.singleShot(0, self._scan_next_address)

    def send_raw(self, payload: bytes) -> None:
        if self.simulation:
            self.serial_event.emit("TX", payload, "tx", "Simulation raw TX only")
            return
        self.request_raw.emit(payload, self.timeout_ms)

    def start_acquisition(self) -> None:
        if self.simulation:
            self._simulation_timer.start(self.interval_ms)
        else:
            self._poll_timer.start(self.interval_ms)
        self.status.emit("Acquisition started")

    def stop_acquisition(self) -> None:
        self._poll_timer.stop()
        self._simulation_timer.stop()
        self.status.emit("Acquisition stopped")

    @property
    def acquisition_active(self) -> bool:
        return self._poll_timer.isActive() or self._simulation_timer.isActive()

    def start_logging(self, directory: str | Path) -> None:
        path = self.logger.start(
            directory,
            module_info=self.module_info,
            com_port=self.connected_port,
            interval_ms=self.interval_ms,
            simulation=self.simulation,
        )
        self.logging_changed.emit(True, str(path), self.logger.samples)

    def stop_logging(self) -> None:
        path = str(self.logger.path or "")
        self.logger.stop()
        self.logging_changed.emit(False, path, self.logger.samples)

    def save_settings(self) -> None:
        self.settings.setValue("serial/address", self.address)
        self.settings.setValue("serial/baud_rate", self.baud_rate)
        self.settings.setValue("serial/timeout_ms", self.timeout_ms)
        self.settings.setValue("serial/retries", self.retries)
        self.settings.setValue("acquisition/interval_ms", self.interval_ms)
        self.settings.setValue("graph/history_seconds", self.history_seconds)
        self.settings.setValue("logging/default_dir", self.log_directory)

    def _send(self, frame: bytes, command: Command) -> None:
        if self._pending_command is not None:
            return
        self._pending_command = command
        self.request_transaction.emit(frame, int(command), self.timeout_ms, self.retries)

    def _send_scan_read_info(self, address: int) -> None:
        self._pending_command = Command.READ_INFO
        self.request_transaction.emit(commands.read_info(address), int(Command.READ_INFO), self.timeout_ms, 0)

    def _service_transaction(self, frame: bytes, command: Command, message: str) -> None:
        if self.simulation:
            ack = CommandAck(int(command), self.address, True, AckStatus.SUCCESS)
            self.ack_received.emit(ack)
            return
        self._polling_before_service = self.acquisition_active
        self.stop_acquisition()
        self.status.emit(message)
        self._send(frame, command)

    def _on_opened(self, port: str) -> None:
        self.connected_port = port
        self.connected.emit(port)
        self.status.emit(f"Connected to {port}")
        self.read_module_info()

    def _on_closed(self) -> None:
        self.connected_port = ""
        self._pending_command = None
        self.disconnected.emit()

    def _on_connection_lost(self, message: str) -> None:
        self.stop_acquisition()
        self.connected_port = ""
        self._pending_command = None
        self.connection_lost.emit(f"Connection lost: {message}")

    def _on_timeout(self, command_value: int) -> None:
        self._pending_command = None
        if self._scan_active:
            QTimer.singleShot(20, self._scan_next_address)
            return
        if self._expected_new_address is not None:
            failed = self._expected_new_address
            self._expected_new_address = None
            self.error.emit(f"Address change verification failed: no response at 0x{failed:02X}")
            self._resume_after_service()
            return
        if self._expected_calibration_gas is not None and command_value == int(Command.READ_INFO):
            requested = self._expected_calibration_gas
            self._expected_calibration_gas = None
            self.error.emit(f"Calibration gas verification failed: no module information response after setting {requested}")
            self._resume_after_service()
            return
        self.error.emit(f"Timeout waiting for 0x{command_value:02X}")
        self._resume_after_service()

    def _on_frame(self, frame: Frame) -> None:
        command = frame.command
        self._pending_command = None
        try:
            if command == Command.READ_INFO:
                info = decode_module_info(frame)
                if self._scan_active:
                    self._scan_results.append(info)
                    self.scan_found.emit(info)
                    QTimer.singleShot(20, self._scan_next_address)
                    return
                self.module_info = info
                self.module_info_received.emit(self.module_info)
                if self._expected_new_address is not None:
                    if self.module_info.address == self._expected_new_address:
                        self.status.emit(f"Address change verified at 0x{self.module_info.address:02X}")
                    else:
                        self.error.emit(
                            "Address change verification failed: "
                            f"requested 0x{self._expected_new_address:02X}, module reports 0x{self.module_info.address:02X}"
                        )
                    self._expected_new_address = None
                    self._resume_after_service()
                if self._expected_calibration_gas is not None:
                    if self.module_info.calibration_concentration == self._expected_calibration_gas:
                        self.status.emit("Calibration gas concentration verified")
                    else:
                        self.error.emit(
                            "Calibration gas verification failed: "
                            f"requested {self._expected_calibration_gas}, module reports {self.module_info.calibration_concentration}"
                        )
                    self._expected_calibration_gas = None
                    self._resume_after_service()
            elif command == Command.READ_CONCENTRATION:
                unit = self.module_info.unit_name if self.module_info else ""
                sensor_type = self.module_info.sensor_type_name if self.module_info else "Unknown"
                reading = decode_gas_reading(frame, expected_address=self.address, unit=unit, sensor_type=sensor_type)
                self._publish_reading(reading)
            elif command in (Command.ZERO, Command.CALIBRATE, Command.CHANGE_ADDRESS, Command.SET_CAL_GAS):
                expected = command if isinstance(command, Command) else Command(command)
                ack = decode_ack(frame, expected)
                self.ack_received.emit(ack)
                if ack.success and expected == Command.CHANGE_ADDRESS:
                    self.address = frame.address
                    self.save_settings()
                    self.read_module_info()
                    return
                elif ack.success and expected == Command.SET_CAL_GAS:
                    self.read_module_info()
                    return
                self._resume_after_service()
            else:
                self.error.emit(f"Unexpected response: {hex_bytes(frame.raw)}")
        except ProtocolError as exc:
            self.error.emit(str(exc))
            if self._scan_active:
                QTimer.singleShot(20, self._scan_next_address)
                return
            self._resume_after_service()

    def _scan_next_address(self) -> None:
        if not self._scan_active:
            return
        if not self._scan_queue:
            self._scan_active = False
            self.address = self._address_before_scan
            self.save_settings()
            self.scan_finished.emit(self._scan_results)
            self.status.emit(f"Address scan finished. Found {len(self._scan_results)} device(s).")
            if self._polling_before_scan:
                self._polling_before_scan = False
                self.start_acquisition()
            return
        address = self._scan_queue.pop(0)
        self.address = address
        self.scan_progress.emit(address)
        self._send_scan_read_info(address)

    def _resume_after_service(self) -> None:
        if self._polling_before_service:
            self._polling_before_service = False
            self.start_acquisition()

    def _publish_reading(self, reading: GasReading) -> None:
        self.reading_received.emit(reading)
        if self.logger.active and reading.status == "OK":
            self.logger.write(reading)
            self.logging_changed.emit(True, str(self.logger.path), self.logger.samples)

    def _emit_simulated_reading(self) -> None:
        if not self.module_info:
            return
        self._simulation_t += self.interval_ms / 1000.0
        baseline = 0.35 + 0.15 * math.sin(self._simulation_t / 12.0)
        noise = self._rng.uniform(-0.025, 0.025)
        value = max(-0.05, baseline + noise)
        reading = GasReading(
            address=self.address,
            value=round(value, 2),
            unit=self.module_info.unit_name,
            timestamp=datetime.now(),
            sensor_type=self.module_info.sensor_type_name,
            simulated=True,
        )
        self.serial_event.emit("RX", b"", "simulation", "Simulated reading")
        self._publish_reading(reading)
