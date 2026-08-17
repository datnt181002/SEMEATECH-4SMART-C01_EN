"""Main window for the 4SMART-C01 Sensor Utility."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.communication.sensor_controller import SensorController
from app.protocol.commands import Command
from app.protocol.models import CommandAck, GasReading, ModuleInfo
from app.widgets.realtime_panel import RealtimePanel
from app.widgets.serial_monitor import SerialMonitor
from app.widgets.service_panel import ServicePanel


INTERVALS = {
    "100 ms": 100,
    "200 ms": 200,
    "500 ms": 500,
    "1 s": 1000,
    "2 s": 2000,
    "5 s": 5000,
}


class SettingsDialog(QDialog):
    def __init__(self, controller: SensorController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)
        root = QVBoxLayout(self)

        serial = QGroupBox("Serial")
        serial_form = QFormLayout(serial)
        self.baud = QSpinBox()
        self.baud.setRange(1200, 921600)
        self.baud.setValue(controller.baud_rate)
        self.timeout = QSpinBox()
        self.timeout.setRange(50, 10000)
        self.timeout.setValue(controller.timeout_ms)
        self.timeout.setSuffix(" ms")
        self.retries = QSpinBox()
        self.retries.setRange(0, 10)
        self.retries.setValue(controller.retries)
        serial_form.addRow("Baud rate:", self.baud)
        serial_form.addRow("Timeout:", self.timeout)
        serial_form.addRow("Retries:", self.retries)
        root.addWidget(serial)

        acquisition = QGroupBox("Acquisition")
        acquisition_form = QFormLayout(acquisition)
        self.interval = QComboBox()
        for label, value in INTERVALS.items():
            self.interval.addItem(label, value)
        index = self.interval.findData(controller.interval_ms)
        self.interval.setCurrentIndex(max(index, 0))
        acquisition_form.addRow("Polling interval:", self.interval)
        root.addWidget(acquisition)

        graph = QGroupBox("Graph")
        graph_form = QFormLayout(graph)
        self.history = QComboBox()
        for label, seconds in [("1 min", 60), ("5 min", 300), ("15 min", 900), ("30 min", 1800), ("1 hour", 3600), ("All", 0)]:
            self.history.addItem(label, seconds)
        index = self.history.findData(controller.history_seconds)
        self.history.setCurrentIndex(max(index, 1))
        graph_form.addRow("History:", self.history)
        root.addWidget(graph)

        logging = QGroupBox("Logging")
        logging_form = QFormLayout(logging)
        log_row = QHBoxLayout()
        self.log_dir = QLineEdit(controller.log_directory)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        log_row.addWidget(self.log_dir, 1)
        log_row.addWidget(browse)
        logging_form.addRow("Default log directory:", log_row)
        root.addWidget(logging)

        buttons = QHBoxLayout()
        buttons.addStretch()
        ok = QPushButton("OK")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        root.addLayout(buttons)

    def accept(self) -> None:
        self.controller.baud_rate = self.baud.value()
        self.controller.timeout_ms = self.timeout.value()
        self.controller.retries = self.retries.value()
        self.controller.interval_ms = int(self.interval.currentData())
        self.controller.history_seconds = int(self.history.currentData())
        self.controller.log_directory = self.log_dir.text()
        self.controller.save_settings()
        super().accept()

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Default Log Directory", self.log_dir.text())
        if path:
            self.log_dir.setText(path)


class SafetyDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About / Safety")
        self.setMinimumSize(620, 460)
        root = QVBoxLayout(self)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(
            """
            <h2>4SMART-C01 Sensor Utility</h2>
            <p>Protocol source: SemeaTech 4SMART-C01 Sensor Module Application Note AN230526, REV 1.4.</p>
            <h3>Safety Notes From The Manual</h3>
            <ul>
              <li>The module does not have intrinsic-safety certification.</li>
              <li>The module does not have explosion-proof certification.</li>
              <li>Do not use this product in hazardous locations as such.</li>
              <li>The module does not have reverse-polarity protection.</li>
              <li>The module does not have ESD protection.</li>
              <li>Use a stable DC power supply. The manufacturer recommends output fluctuation below 1%.</li>
            </ul>
            <h3>Electrical Interface</h3>
            <p>Operating voltage: 3.3-5.5 VDC<br>
            UART electrical level: 3.0 V TTL</p>
            <p><b>3.0 V TTL UART is not RS-232 voltage level.</b> Use a compatible USB-UART adapter.</p>
            <p>This software is a diagnostic and calibration utility. It does not provide explosion safety or certified gas-monitoring functionality.</p>
            """
        )
        root.addWidget(text)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        root.addWidget(close, alignment=Qt.AlignRight)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("4SMART-C01 Sensor Utility")
        self.resize(1180, 820)
        self.controller = SensorController()
        self._connected = False
        self._software_low_alarm = float(self.controller.settings.value("alarm/software_low", 1.0))
        self._software_high_alarm = float(self.controller.settings.value("alarm/software_high", 2.0))
        self._setup_ui()
        self._connect_signals()
        self.dashboard.set_software_thresholds(self._software_low_alarm, self._software_high_alarm)
        self.service.set_software_alarm_values(self._software_low_alarm, self._software_high_alarm)
        self.refresh_ports()
        self._apply_style()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.controller.shutdown()
        event.accept()

    def _setup_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        self.setCentralWidget(central)

        title = QLabel("4SMART-C01 Sensor Utility")
        title.setObjectName("appTitle")
        root.addWidget(title)

        connection = QGroupBox()
        connection.setMinimumHeight(78)
        connection_layout = QHBoxLayout(connection)
        connection_layout.setContentsMargins(12, 18, 12, 10)
        connection_layout.setSpacing(8)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(180)
        self.port_combo.setMaximumWidth(420)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setMinimumWidth(76)
        self.baud_label = QLabel("Baud: 9600")
        self.baud_label.setMinimumWidth(86)
        self.address_spin = QSpinBox()
        self.address_spin.setRange(0, 255)
        self.address_spin.setValue(self.controller.address)
        self.address_spin.setDisplayIntegerBase(16)
        self.address_spin.setMinimumWidth(82)
        self.connect_button = QPushButton("Connect")
        self.connect_button.setMinimumWidth(92)
        self.simulation_check = QCheckBox("Simulation Mode")
        self.simulation_check.setMinimumWidth(130)
        self.state_label = QLabel("DISCONNECTED")
        self.state_label.setObjectName("stateLabel")
        self.state_label.setMinimumWidth(112)
        connection_layout.addWidget(QLabel("COM Port:"))
        connection_layout.addWidget(self.port_combo)
        connection_layout.addWidget(self.refresh_button)
        connection_layout.addWidget(self.baud_label)
        connection_layout.addWidget(QLabel("Address:"))
        connection_layout.addWidget(self.address_spin)
        connection_layout.addWidget(self.simulation_check)
        connection_layout.addWidget(self.connect_button)
        connection_layout.addWidget(self.state_label)
        connection_layout.addStretch()
        root.addWidget(connection)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.start_button = QPushButton("Start Acquisition")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.start_log_button = QPushButton("Start Logging")
        self.stop_log_button = QPushButton("Stop Logging")
        self.stop_log_button.setEnabled(False)
        self.settings_button = QPushButton("Settings")
        self.safety_button = QPushButton("About / Safety")
        self.log_label = QLabel("Logging: OFF")
        self.log_label.setMinimumWidth(260)
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        actions.addWidget(self.start_log_button)
        actions.addWidget(self.stop_log_button)
        actions.addStretch()
        actions.addWidget(self.log_label)
        actions.addWidget(self.settings_button)
        actions.addWidget(self.safety_button)
        root.addLayout(actions)

        self.tabs = QTabWidget()
        self.dashboard = RealtimePanel()
        self.service = ServicePanel()
        self.monitor = SerialMonitor()
        self.tabs.addTab(self.dashboard, "Dashboard")
        self.tabs.addTab(self.service, "Service")
        self.tabs.addTab(self.monitor, "Serial Monitor")
        root.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.counter_label = QLabel("OK 0 | CRC 0 | Timeouts 0 | Malformed 0")
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.counter_label)
        root.addLayout(footer)

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self.refresh_ports)
        self.connect_button.clicked.connect(self._toggle_connection)
        self.address_spin.valueChanged.connect(self._address_changed)
        self.start_button.clicked.connect(self._start_acquisition)
        self.stop_button.clicked.connect(self._stop_acquisition)
        self.start_log_button.clicked.connect(self._start_logging)
        self.stop_log_button.clicked.connect(self.controller.stop_logging)
        self.settings_button.clicked.connect(self._settings)
        self.safety_button.clicked.connect(self._safety)

        self.service.read_info_requested.connect(self.controller.read_module_info)
        self.service.zero_requested.connect(self._confirm_zero)
        self.service.calibrate_requested.connect(self._confirm_calibration)
        self.service.set_calibration_requested.connect(self._confirm_set_calibration)
        self.service.change_address_requested.connect(self._confirm_change_address)
        self.service.scan_requested.connect(self._scan_addresses)
        self.service.use_scanned_address_requested.connect(self._use_scanned_address)
        self.service.software_alarm_changed.connect(self._set_software_alarm)
        self.monitor.raw_send_requested.connect(self.controller.send_raw)

        self.controller.connected.connect(self._on_connected)
        self.controller.disconnected.connect(self._on_disconnected)
        self.controller.connection_lost.connect(self._on_connection_lost)
        self.controller.module_info_received.connect(self._on_module_info)
        self.controller.reading_received.connect(self._on_reading)
        self.controller.ack_received.connect(self._on_ack)
        self.controller.error.connect(self._show_error)
        self.controller.status.connect(self.status_label.setText)
        self.controller.serial_event.connect(self.monitor.append_event)
        self.controller.counters_changed.connect(self._on_counters)
        self.controller.logging_changed.connect(self._on_logging_changed)
        self.controller.scan_started.connect(self.service.clear_scan_results)
        self.controller.scan_progress.connect(self.service.update_scan_progress)
        self.controller.scan_found.connect(self.service.add_scan_result)
        self.controller.scan_finished.connect(lambda results: self.service.finish_scan(len(results)))

    def refresh_ports(self) -> None:
        current = self.port_combo.currentText()
        self.port_combo.clear()
        ports = self.controller.available_ports()
        self.port_combo.addItems(ports)
        if current:
            index = self.port_combo.findText(current)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
        if not ports:
            self.port_combo.addItem("No COM ports")

    def _toggle_connection(self) -> None:
        if self._connected:
            self.controller.disconnect_sensor()
            return
        self.controller.address = self.address_spin.value()
        self.controller.baud_rate = int(self.baud_label.text().split(":")[1].strip())
        self.controller.save_settings()
        if self.simulation_check.isChecked():
            self.controller.connect_sensor("SIMULATION", simulation=True)
            return
        port = self.port_combo.currentText()
        if not port or port == "No COM ports":
            QMessageBox.warning(self, "No COM Port", "Select a COM port or enable Simulation Mode.")
            return
        self.controller.connect_sensor(port)

    def _address_changed(self, value: int) -> None:
        self.controller.address = value
        self.controller.save_settings()

    def _start_acquisition(self) -> None:
        if not self._connected:
            QMessageBox.warning(self, "Not Connected", "Connect to the module or enable Simulation Mode first.")
            return
        self.controller.start_acquisition()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def _stop_acquisition(self) -> None:
        self.controller.stop_acquisition()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _start_logging(self) -> None:
        if not self._connected:
            QMessageBox.warning(self, "Not Connected", "Connect before starting a log.")
            return
        directory = QFileDialog.getExistingDirectory(self, "Select Log Directory", self.controller.log_directory)
        if directory:
            self.controller.start_logging(directory)

    def _settings(self) -> None:
        dialog = SettingsDialog(self.controller, self)
        if dialog.exec():
            self.baud_label.setText(f"Baud: {self.controller.baud_rate}")
            self.controller.save_settings()

    def _safety(self) -> None:
        SafetyDialog(self).exec()

    def _confirm_zero(self) -> None:
        if QMessageBox.warning(
            self,
            "Zero Sensor",
            "Zero-setting modifies sensor calibration.\n\nEnsure the sensor is exposed to the correct zero/reference environment specified for the installed electrochemical sensor.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes:
            self.controller.zero()

    def _confirm_calibration(self) -> None:
        if QMessageBox.warning(
            self,
            "Calibrate Sensor",
            "Calibration changes the sensor's measurement calibration.\n\nBefore continuing:\n- Apply the correct certified calibration gas.\n- Verify the configured calibration-gas concentration.\n- Allow gas flow and stabilization according to the sensor manufacturer's requirements.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes:
            self.controller.calibrate()

    def _confirm_set_calibration(self, concentration: int) -> None:
        if QMessageBox.question(
            self,
            "Set Calibration Gas",
            f"Set calibration gas concentration to {concentration}?\n\nThe utility will read module information again after a successful write.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes:
            self.controller.set_calibration_gas(concentration)

    def _confirm_change_address(self, new_address: int) -> None:
        if QMessageBox.question(
            self,
            "Change Address",
            f"Change module address to 0x{new_address:02X}?\n\nThe utility will verify communication at the new address.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes:
            self.controller.change_address(new_address)

    def _scan_addresses(self, start_address: int, end_address: int) -> None:
        if not self._connected:
            QMessageBox.warning(self, "Not Connected", "Connect to the COM port or enable Simulation Mode before scanning.")
            return
        self.controller.scan_addresses(start_address, end_address)

    def _use_scanned_address(self, address: int) -> None:
        self.address_spin.blockSignals(True)
        self.address_spin.setValue(address)
        self.address_spin.blockSignals(False)
        self.controller.address = address
        self.controller.save_settings()
        self.status_label.setText(f"Using scanned address 0x{address:02X}")
        self.controller.read_module_info()

    def _set_software_alarm(self, low_alarm: float, high_alarm: float) -> None:
        if low_alarm > high_alarm:
            QMessageBox.warning(self, "Invalid Alarm Thresholds", "Low alarm must be less than or equal to High alarm.")
            return
        self._software_low_alarm = low_alarm
        self._software_high_alarm = high_alarm
        self.controller.settings.setValue("alarm/software_low", low_alarm)
        self.controller.settings.setValue("alarm/software_high", high_alarm)
        self.dashboard.set_software_thresholds(low_alarm, high_alarm)
        unit = self.controller.module_info.unit_name if self.controller.module_info else ""
        self.status_label.setText(f"Software display alarm set: Low {low_alarm:g} {unit}, High {high_alarm:g} {unit}")

    def _on_connected(self, port: str) -> None:
        self._connected = True
        self.connect_button.setText("Disconnect")
        self.state_label.setText("CONNECTED" if port != "SIMULATION" else "SIMULATION")
        self.state_label.setProperty("connected", True)
        self._refresh_state_label()

    def _on_disconnected(self) -> None:
        self._connected = False
        self.connect_button.setText("Connect")
        self.state_label.setText("DISCONNECTED")
        self.state_label.setProperty("connected", False)
        self._refresh_state_label()
        self._stop_acquisition()

    def _on_connection_lost(self, message: str) -> None:
        self._on_disconnected()
        QMessageBox.critical(self, "Connection Lost", message)

    def _on_module_info(self, info: ModuleInfo) -> None:
        self.dashboard.update_module_info(info)
        self.service.update_module_info(info)
        self.dashboard.set_software_thresholds(self._software_low_alarm, self._software_high_alarm)
        self.address_spin.blockSignals(True)
        self.address_spin.setValue(info.address)
        self.address_spin.blockSignals(False)
        self.status_label.setText(f"Module information: {info.sensor_type_name}, range {info.measurement_range} {info.unit_name}")

    def _on_reading(self, reading: GasReading) -> None:
        self.dashboard.add_reading(reading)

    def _on_ack(self, ack: CommandAck) -> None:
        command_name = Command(ack.command).name if ack.command in [int(command) for command in Command] else f"0x{ack.command:02X}"
        result = "success" if ack.success else "failure"
        QMessageBox.information(self, "Module Response", f"{command_name}: {result} (0x{ack.status_code:02X})")

    def _show_error(self, message: str) -> None:
        self.status_label.setText(message)
        self.monitor.append_event("ERR", b"", "malformed", message)

    def _on_counters(self, counters: dict) -> None:
        self.counter_label.setText(
            f"OK {counters.get('successful_frames', 0)} | "
            f"CRC {counters.get('crc_errors', 0)} | "
            f"Timeouts {counters.get('timeouts', 0)} | "
            f"Malformed {counters.get('malformed_frames', 0)}"
        )

    def _on_logging_changed(self, active: bool, path: str, samples: int) -> None:
        self.start_log_button.setEnabled(not active)
        self.stop_log_button.setEnabled(active)
        state = "ON" if active else "OFF"
        filename = Path(path).name if path else ""
        self.log_label.setText(f"Logging: {state} | Samples: {samples} | File: {filename}")

    def _refresh_state_label(self) -> None:
        self.state_label.style().unpolish(self.state_label)
        self.state_label.style().polish(self.state_label)

    def _apply_style(self) -> None:
        QApplication.instance().setStyleSheet(
            """
            QWidget {
                font-family: Segoe UI;
                font-size: 10pt;
                color: #172033;
            }
            QMainWindow, QWidget {
                background: #f6f8fb;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d7dee9;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #334155;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #b8c4d6;
                border-radius: 5px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                border-color: #0f766e;
                background: #f0fdfa;
            }
            QPushButton:disabled {
                color: #94a3b8;
                background: #eef2f7;
            }
            QLineEdit, QSpinBox, QComboBox {
                background: #ffffff;
                border: 1px solid #b8c4d6;
                border-radius: 5px;
                padding: 4px 6px;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                background: #ffffff;
                border-radius: 6px;
                top: -1px;
            }
            QTabBar::tab {
                background: #e2e8f0;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-bottom-color: #cbd5e1;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                padding: 7px 16px;
                margin-right: 3px;
                min-width: 110px;
            }
            QTabBar::tab:selected {
                background: #0f766e;
                color: #ffffff;
                border-color: #0f766e;
                font-weight: 600;
            }
            QTabBar::tab:!selected:hover {
                background: #cbd5e1;
                color: #0f172a;
            }
            #appTitle {
                font-size: 20pt;
                font-weight: 700;
                color: #0f172a;
            }
            #sensorName {
                font-size: 22pt;
                font-weight: 700;
            }
            #mainValue {
                font-size: 72pt;
                font-weight: 700;
                color: #0f766e;
            }
            #unitLabel {
                font-size: 22pt;
                color: #475569;
            }
            #infoKey {
                background: #dbe5f0;
                color: #1e293b;
                border: 1px solid #c4d0df;
                border-radius: 4px;
                padding: 7px 10px;
                font-weight: 700;
            }
            #infoValue {
                background: #ffffff;
                color: #0f172a;
                border: 1px solid #d7dee9;
                border-radius: 4px;
                padding: 7px 10px;
            }
            #stateLabel {
                font-weight: 700;
                color: #b91c1c;
            }
            #stateLabel[connected="true"] {
                color: #047857;
            }
            #alarmLabel[alarm="true"] {
                color: #b91c1c;
                font-weight: 700;
            }
            #statValue {
                font-size: 15pt;
                font-weight: 600;
            }
            QTextEdit {
                background: #0f172a;
                color: #e5e7eb;
                font-family: Consolas;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
            """
        )
