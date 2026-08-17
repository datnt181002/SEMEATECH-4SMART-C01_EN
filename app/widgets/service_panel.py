"""Service and calibration controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.protocol.models import ModuleInfo


class ServicePanel(QWidget):
    read_info_requested = Signal()
    zero_requested = Signal()
    calibrate_requested = Signal()
    change_address_requested = Signal(int)
    set_calibration_requested = Signal(int)
    scan_requested = Signal(int, int)
    use_scanned_address_requested = Signal(int)
    software_alarm_changed = Signal(float, float)

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(14)

        info_group = QGroupBox("Module Information")
        info_group.setMinimumHeight(210)
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(14, 18, 14, 12)
        info_layout.setSpacing(10)
        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(8)
        info_grid.setVerticalSpacing(8)
        info_grid.setColumnMinimumWidth(0, 145)
        info_grid.setColumnMinimumWidth(1, 170)
        info_grid.setColumnMinimumWidth(2, 145)
        info_grid.setColumnMinimumWidth(3, 170)
        info_grid.setColumnStretch(1, 1)
        info_grid.setColumnStretch(3, 1)
        self.info_labels: dict[str, QLabel] = {}
        info_keys = [
            "Address",
            "Sensor type",
            "Range",
            "Calibration gas",
            "High alarm",
            "Low alarm",
            "Unit",
        ]
        for index, key in enumerate(info_keys):
            name = QLabel(key)
            name.setMinimumHeight(34)
            name.setObjectName("infoKey")
            name.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            label = QLabel("--")
            label.setMinimumHeight(34)
            label.setMinimumWidth(130)
            label.setObjectName("infoValue")
            label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            label.setTextInteractionFlags(label.textInteractionFlags() | Qt.TextSelectableByMouse)
            self.info_labels[key] = label
            row = index // 2
            column = (index % 2) * 2
            info_grid.addWidget(name, row, column)
            info_grid.addWidget(label, row, column + 1)
        info_layout.addLayout(info_grid)
        self.read_info_button = QPushButton("Read Information")
        self.read_info_button.setMinimumHeight(30)
        self.read_info_button.setMaximumWidth(160)
        info_layout.addWidget(self.read_info_button)
        root.addWidget(info_group)

        zero_group = QGroupBox("Zero")
        zero_group.setMinimumHeight(76)
        zero_layout = QHBoxLayout(zero_group)
        self.zero_button = QPushButton("Zero Sensor")
        self.zero_button.setToolTip("Modifies sensor zero calibration after confirmation.")
        zero_layout.addWidget(self.zero_button)
        zero_layout.addStretch()
        root.addWidget(zero_group)

        cal_gas_group = QGroupBox("Calibration Gas Concentration")
        cal_gas_group.setMinimumHeight(78)
        cal_gas_layout = QHBoxLayout(cal_gas_group)
        self.cal_gas_spin = QSpinBox()
        self.cal_gas_spin.setMinimumWidth(130)
        self.cal_gas_spin.setRange(0, 65535)
        self.cal_gas_spin.setValue(500)
        self.set_cal_gas_button = QPushButton("Set Concentration")
        cal_gas_layout.addWidget(self.cal_gas_spin)
        cal_gas_layout.addWidget(self.set_cal_gas_button)
        cal_gas_layout.addStretch()
        root.addWidget(cal_gas_group)

        calibration_group = QGroupBox("Calibration")
        calibration_group.setMinimumHeight(78)
        calibration_layout = QHBoxLayout(calibration_group)
        self.calibrate_button = QPushButton("Calibrate Sensor")
        self.calibrate_button.setToolTip("Waits for the module's actual calibration response.")
        calibration_layout.addWidget(self.calibrate_button)
        calibration_layout.addStretch()
        root.addWidget(calibration_group)

        address_group = QGroupBox("Module Address")
        address_group.setMinimumHeight(82)
        address_layout = QHBoxLayout(address_group)
        self.current_address = QLineEdit("0x01")
        self.current_address.setReadOnly(True)
        self.current_address.setMaximumWidth(150)
        self.new_address = QSpinBox()
        self.new_address.setRange(0, 255)
        self.new_address.setValue(2)
        self.new_address.setDisplayIntegerBase(16)
        self.new_address.setMinimumWidth(100)
        self.change_address_button = QPushButton("Change Address")
        address_layout.addWidget(QLabel("Current"))
        address_layout.addWidget(self.current_address)
        address_layout.addWidget(QLabel("New"))
        address_layout.addWidget(self.new_address)
        address_layout.addWidget(self.change_address_button)
        address_layout.addStretch()
        root.addWidget(address_group)

        scan_group = QGroupBox("Scan Addresses")
        scan_group.setMinimumHeight(220)
        scan_layout = QVBoxLayout(scan_group)
        scan_controls = QHBoxLayout()
        self.scan_start = QSpinBox()
        self.scan_start.setRange(0, 255)
        self.scan_start.setDisplayIntegerBase(16)
        self.scan_start.setValue(1)
        self.scan_start.setMinimumWidth(92)
        self.scan_end = QSpinBox()
        self.scan_end.setRange(0, 255)
        self.scan_end.setDisplayIntegerBase(16)
        self.scan_end.setValue(16)
        self.scan_end.setMinimumWidth(92)
        self.scan_button = QPushButton("Scan")
        self.use_scanned_button = QPushButton("Use Selected Address")
        scan_controls.addWidget(QLabel("From"))
        scan_controls.addWidget(self.scan_start)
        scan_controls.addWidget(QLabel("To"))
        scan_controls.addWidget(self.scan_end)
        scan_controls.addWidget(self.scan_button)
        scan_controls.addWidget(self.use_scanned_button)
        scan_controls.addStretch()
        scan_layout.addLayout(scan_controls)
        self.scan_status = QLabel("Not scanned")
        scan_layout.addWidget(self.scan_status)
        self.scan_table = QTableWidget(0, 4)
        self.scan_table.setHorizontalHeaderLabels(["Address", "Sensor", "Range", "Unit"])
        self.scan_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.scan_table.setMinimumHeight(120)
        self.scan_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scan_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.scan_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.scan_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        scan_layout.addWidget(self.scan_table)
        root.addWidget(scan_group)

        software_alarm_group = QGroupBox("Software Display Alarm")
        software_alarm_group.setMinimumHeight(82)
        software_alarm_layout = QHBoxLayout(software_alarm_group)
        self.software_low_spin = QDoubleSpinBox()
        self.software_low_spin.setRange(-65535.99, 65535.99)
        self.software_low_spin.setDecimals(2)
        self.software_low_spin.setMinimumWidth(140)
        self.software_high_spin = QDoubleSpinBox()
        self.software_high_spin.setRange(-65535.99, 65535.99)
        self.software_high_spin.setDecimals(2)
        self.software_high_spin.setMinimumWidth(140)
        self.apply_alarm_button = QPushButton("Apply")
        software_alarm_layout.addWidget(QLabel("Low"))
        software_alarm_layout.addWidget(self.software_low_spin)
        software_alarm_layout.addWidget(QLabel("High"))
        software_alarm_layout.addWidget(self.software_high_spin)
        software_alarm_layout.addWidget(self.apply_alarm_button)
        software_alarm_layout.addStretch()
        root.addWidget(software_alarm_group)
        root.addStretch()

        self.read_info_button.clicked.connect(self.read_info_requested)
        self.zero_button.clicked.connect(self.zero_requested)
        self.calibrate_button.clicked.connect(self.calibrate_requested)
        self.set_cal_gas_button.clicked.connect(lambda: self.set_calibration_requested.emit(self.cal_gas_spin.value()))
        self.change_address_button.clicked.connect(lambda: self.change_address_requested.emit(self.new_address.value()))
        self.scan_button.clicked.connect(lambda: self.scan_requested.emit(self.scan_start.value(), self.scan_end.value()))
        self.use_scanned_button.clicked.connect(self._use_selected_scan_address)
        self.apply_alarm_button.clicked.connect(
            lambda: self.software_alarm_changed.emit(self.software_low_spin.value(), self.software_high_spin.value())
        )

    def update_module_info(self, info: ModuleInfo) -> None:
        self.info_labels["Address"].setText(f"0x{info.address:02X}")
        self.info_labels["Sensor type"].setText(f"{info.sensor_type_name} (0x{info.sensor_type_code:02X})")
        self.info_labels["Range"].setText(f"{info.measurement_range} {info.unit_name}")
        self.info_labels["Calibration gas"].setText(f"{info.calibration_concentration} {info.unit_name}")
        self.info_labels["High alarm"].setText(f"{info.high_alarm} {info.unit_name}")
        self.info_labels["Low alarm"].setText(f"{info.low_alarm} {info.unit_name}")
        self.info_labels["Unit"].setText(info.unit_name)
        self.current_address.setText(f"0x{info.address:02X}")
        self.cal_gas_spin.setValue(info.calibration_concentration)
        self.software_low_spin.setSuffix(f" {info.unit_name}")
        self.software_high_spin.setSuffix(f" {info.unit_name}")

    def set_software_alarm_values(self, low_alarm: float, high_alarm: float) -> None:
        self.software_low_spin.setValue(low_alarm)
        self.software_high_spin.setValue(high_alarm)

    def clear_scan_results(self, start_address: int, end_address: int) -> None:
        self.scan_table.setRowCount(0)
        self.scan_button.setEnabled(False)
        self.scan_status.setText(f"Scanning 0x{start_address:02X}-0x{end_address:02X}...")

    def update_scan_progress(self, address: int) -> None:
        self.scan_status.setText(f"Scanning address 0x{address:02X}...")

    def add_scan_result(self, info: ModuleInfo) -> None:
        row = self.scan_table.rowCount()
        self.scan_table.insertRow(row)
        values = [
            f"0x{info.address:02X}",
            info.sensor_type_name,
            str(info.measurement_range),
            info.unit_name,
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 0:
                item.setData(256, info.address)
            self.scan_table.setItem(row, column, item)
        self.scan_table.resizeColumnsToContents()

    def finish_scan(self, count: int) -> None:
        self.scan_button.setEnabled(True)
        self.scan_status.setText(f"Scan complete. Found {count} device(s).")

    def _use_selected_scan_address(self) -> None:
        row = self.scan_table.currentRow()
        if row < 0:
            return
        item = self.scan_table.item(row, 0)
        if item is None:
            return
        address = int(item.data(256))
        self.use_scanned_address_requested.emit(address)
