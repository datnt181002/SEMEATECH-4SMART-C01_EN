"""Dashboard widget for live concentration, statistics, and graph."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.protocol.models import GasReading, ModuleInfo


@dataclass
class RunningStats:
    samples: int = 0
    minimum: float | None = None
    maximum: float | None = None
    total: float = 0.0

    def add(self, value: float) -> None:
        self.samples += 1
        self.total += value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)

    @property
    def average(self) -> float | None:
        if not self.samples:
            return None
        return self.total / self.samples


class RealtimePanel(QWidget):
    reset_statistics_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.module_info: ModuleInfo | None = None
        self.software_low_alarm: float | None = None
        self.software_high_alarm: float | None = None
        self.stats = RunningStats()
        self._points: deque[tuple[datetime, float]] = deque(maxlen=72000)
        self._high_line = pg.InfiniteLine(angle=0, pen=pg.mkPen("#d97706", width=1, style=Qt.DashLine))
        self._low_line = pg.InfiniteLine(angle=0, pen=pg.mkPen("#2563eb", width=1, style=Qt.DashLine))
        self._high_line_added = False
        self._low_line_added = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        self.sensor_label = QLabel("Unknown")
        self.sensor_label.setObjectName("sensorName")
        self.value_label = QLabel("--")
        self.value_label.setObjectName("mainValue")
        self.unit_label = QLabel("")
        self.unit_label.setObjectName("unitLabel")
        self.alarm_label = QLabel("Software display alarm: inactive")
        self.alarm_label.setObjectName("alarmLabel")

        hero = QGroupBox()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(self.sensor_label, alignment=Qt.AlignCenter)
        hero_layout.addWidget(self.value_label, alignment=Qt.AlignCenter)
        hero_layout.addWidget(self.unit_label, alignment=Qt.AlignCenter)
        hero_layout.addWidget(self.alarm_label, alignment=Qt.AlignCenter)

        self.info_labels: dict[str, QLabel] = {}
        info = QGroupBox("Module Information")
        info_grid = QGridLayout(info)
        info_grid.setHorizontalSpacing(8)
        info_grid.setVerticalSpacing(8)
        for row, key in enumerate(["Range", "Calibration", "High alarm", "Low alarm", "Module address"]):
            name = QLabel(key)
            name.setObjectName("infoKey")
            name.setMinimumHeight(38)
            name.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            label = QLabel("--")
            label.setObjectName("infoValue")
            label.setMinimumHeight(38)
            label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.info_labels[key] = label
            info_grid.addWidget(name, row // 2, (row % 2) * 2)
            info_grid.addWidget(label, row // 2, (row % 2) * 2 + 1)

        top = QHBoxLayout()
        top.addWidget(hero, 2)
        top.addWidget(info, 1)
        root.addLayout(top)

        controls = QHBoxLayout()
        self.history_combo = QComboBox()
        self.history_combo.addItems(["1 min", "5 min", "15 min", "30 min", "1 hour", "All"])
        self.history_combo.setCurrentText("5 min")
        self.high_alarm_check = QCheckBox("High alarm line")
        self.low_alarm_check = QCheckBox("Low alarm line")
        self.auto_scale_check = QCheckBox("Auto scale Y")
        self.auto_scale_check.setChecked(True)
        controls.addWidget(QLabel("History"))
        controls.addWidget(self.history_combo)
        controls.addWidget(self.high_alarm_check)
        controls.addWidget(self.low_alarm_check)
        controls.addWidget(self.auto_scale_check)
        controls.addStretch()
        root.addLayout(controls)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("#ffffff")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Time", units="s")
        self.plot.setLabel("left", "Concentration")
        self.curve = self.plot.plot([], [], pen=pg.mkPen("#0f766e", width=2))
        root.addWidget(self.plot, 1)

        stats_group = QGroupBox("Statistics")
        stats_layout = QGridLayout(stats_group)
        self.stat_labels: dict[str, QLabel] = {}
        for col, key in enumerate(["Current", "Minimum", "Maximum", "Average", "Samples"]):
            stats_layout.addWidget(QLabel(key), 0, col)
            value = QLabel("--")
            value.setObjectName("statValue")
            self.stat_labels[key] = value
            stats_layout.addWidget(value, 1, col)
        self.reset_button = QPushButton("Reset Statistics")
        self.reset_button.clicked.connect(self.reset_statistics)
        stats_layout.addWidget(self.reset_button, 0, 5, 2, 1)
        root.addWidget(stats_group)

        self.high_alarm_check.toggled.connect(self._update_alarm_lines)
        self.low_alarm_check.toggled.connect(self._update_alarm_lines)
        self.auto_scale_check.toggled.connect(self._refresh_plot)
        self.history_combo.currentTextChanged.connect(lambda _: self._refresh_plot())

    def update_module_info(self, info: ModuleInfo) -> None:
        self.module_info = info
        if self.software_low_alarm is None:
            self.software_low_alarm = float(info.low_alarm)
        if self.software_high_alarm is None:
            self.software_high_alarm = float(info.high_alarm)
        self.sensor_label.setText(info.sensor_type_name)
        self.unit_label.setText(info.unit_name)
        self.plot.setLabel("left", "Concentration", units=info.unit_name)
        self.info_labels["Range"].setText(f"{info.measurement_range} {info.unit_name}")
        self.info_labels["Calibration"].setText(f"{info.calibration_concentration} {info.unit_name}")
        self.info_labels["High alarm"].setText(f"{info.high_alarm} {info.unit_name}")
        self.info_labels["Low alarm"].setText(f"{info.low_alarm} {info.unit_name}")
        self.info_labels["Module address"].setText(f"0x{info.address:02X}")
        self._high_line.setValue(self.software_high_alarm)
        self._low_line.setValue(self.software_low_alarm)
        self._update_alarm_lines()

    def set_software_thresholds(self, low_alarm: float | None, high_alarm: float | None) -> None:
        self.software_low_alarm = low_alarm
        self.software_high_alarm = high_alarm
        if high_alarm is not None:
            self._high_line.setValue(high_alarm)
        if low_alarm is not None:
            self._low_line.setValue(low_alarm)
        self._update_alarm_lines()

    def add_reading(self, reading: GasReading) -> None:
        self._points.append((reading.timestamp, reading.value))
        self.stats.add(reading.value)
        self.value_label.setText(f"{reading.value:.2f}")
        self.unit_label.setText(reading.unit)
        self.stat_labels["Current"].setText(f"{reading.value:.2f}")
        self.stat_labels["Minimum"].setText(self._format(self.stats.minimum))
        self.stat_labels["Maximum"].setText(self._format(self.stats.maximum))
        self.stat_labels["Average"].setText(self._format(self.stats.average))
        self.stat_labels["Samples"].setText(str(self.stats.samples))
        self._update_alarm_state(reading.value)
        self._refresh_plot()

    def reset_statistics(self) -> None:
        self.stats = RunningStats()
        self._points.clear()
        self.value_label.setText("--")
        for label in self.stat_labels.values():
            label.setText("--")
        self._refresh_plot()

    def _history_seconds(self) -> int | None:
        return {
            "1 min": 60,
            "5 min": 300,
            "15 min": 900,
            "30 min": 1800,
            "1 hour": 3600,
            "All": None,
        }[self.history_combo.currentText()]

    def _refresh_plot(self) -> None:
        if not self._points:
            self.curve.setData([], [])
            return
        latest = self._points[-1][0]
        window = self._history_seconds()
        filtered = [
            (timestamp, value)
            for timestamp, value in self._points
            if window is None or (latest - timestamp).total_seconds() <= window
        ]
        x = [(timestamp - latest).total_seconds() for timestamp, _ in filtered]
        y = [value for _, value in filtered]
        self.curve.setData(x, y)
        if self.auto_scale_check.isChecked():
            self.plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)

    def _update_alarm_lines(self) -> None:
        for line, checkbox, attr in (
            (self._high_line, self.high_alarm_check, "_high_line_added"),
            (self._low_line, self.low_alarm_check, "_low_line_added"),
        ):
            added = bool(getattr(self, attr))
            if checkbox.isChecked() and not added:
                self.plot.addItem(line)
                setattr(self, attr, True)
            elif not checkbox.isChecked() and added:
                self.plot.removeItem(line)
                setattr(self, attr, False)

    def _update_alarm_state(self, value: float) -> None:
        low_alarm = self.software_low_alarm
        high_alarm = self.software_high_alarm
        if low_alarm is None and self.module_info:
            low_alarm = float(self.module_info.low_alarm)
        if high_alarm is None and self.module_info:
            high_alarm = float(self.module_info.high_alarm)
        if low_alarm is None or high_alarm is None:
            self.alarm_label.setText("Software display alarm: inactive")
            self.alarm_label.setProperty("alarm", False)
            self.alarm_label.style().unpolish(self.alarm_label)
            self.alarm_label.style().polish(self.alarm_label)
            return
        active = value >= high_alarm or value <= low_alarm
        self.alarm_label.setText("Software display alarm: active" if active else "Software display alarm: inactive")
        self.alarm_label.setProperty("alarm", active)
        self.alarm_label.style().unpolish(self.alarm_label)
        self.alarm_label.style().polish(self.alarm_label)

    @staticmethod
    def _format(value: float | None) -> str:
        return "--" if value is None else f"{value:.2f}"
