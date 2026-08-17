"""Decoded protocol data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ModuleInfo:
    address: int
    sensor_type_code: int
    sensor_type_name: str
    measurement_range: int
    calibration_concentration: int
    high_alarm: int
    low_alarm: int
    unit_code: int
    unit_name: str


@dataclass(frozen=True)
class GasReading:
    address: int
    value: float
    unit: str
    timestamp: datetime
    sensor_type: str = "Unknown"
    status: str = "OK"
    simulated: bool = False


@dataclass(frozen=True)
class CommandAck:
    command: int
    address: int
    success: bool
    status_code: int
    concentration: int | None = None


@dataclass
class ErrorCounters:
    successful_frames: int = 0
    crc_errors: int = 0
    timeouts: int = 0
    malformed_frames: int = 0

