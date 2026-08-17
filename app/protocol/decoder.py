"""High-level protocol decoders."""

from __future__ import annotations

from datetime import datetime

from .commands import AckStatus, Command
from .frames import Frame
from .models import CommandAck, GasReading, ModuleInfo
from .sensor_types import sensor_name, unit_name


class ProtocolError(ValueError):
    """Raised when a valid frame cannot be interpreted for the expected command."""


def _u16(high: int, low: int) -> int:
    return (high << 8) | low


def decode_module_info(frame: Frame) -> ModuleInfo:
    if frame.command != Command.READ_INFO:
        raise ProtocolError(f"Expected READ_INFO, got {frame.command!r}")
    if len(frame.data) != 10:
        raise ProtocolError(f"Module information response has {len(frame.data)} data bytes; expected 10")
    data = frame.data
    sensor_code = data[0]
    unit_code = data[9]
    return ModuleInfo(
        address=frame.address,
        sensor_type_code=sensor_code,
        sensor_type_name=sensor_name(sensor_code),
        measurement_range=_u16(data[1], data[2]),
        calibration_concentration=_u16(data[3], data[4]),
        high_alarm=_u16(data[5], data[6]),
        low_alarm=_u16(data[7], data[8]),
        unit_code=unit_code,
        unit_name=unit_name(unit_code),
    )


def decode_gas_reading(
    frame: Frame,
    *,
    expected_address: int | None = None,
    unit: str = "",
    sensor_type: str = "Unknown",
    timestamp: datetime | None = None,
    simulated: bool = False,
) -> GasReading:
    if frame.command != Command.READ_CONCENTRATION:
        raise ProtocolError(f"Expected READ_CONCENTRATION, got {frame.command!r}")
    if expected_address is not None and frame.address != expected_address:
        raise ProtocolError(f"Unexpected address 0x{frame.address:02X}; expected 0x{expected_address:02X}")
    if len(frame.data) != 4:
        raise ProtocolError(f"Concentration response has {len(frame.data)} data bytes; expected 4")

    sign, high, low, fraction = frame.data
    if sign not in (0x00, 0x80):
        raise ProtocolError(f"Invalid sign byte 0x{sign:02X}")
    if fraction > 99:
        raise ProtocolError(f"Invalid hundredths byte {fraction}; expected 0..99")

    value = _u16(high, low) + fraction / 100.0
    if sign == 0x80:
        value = -value
    return GasReading(
        address=frame.address,
        value=value,
        unit=unit,
        timestamp=timestamp or datetime.now(),
        sensor_type=sensor_type,
        simulated=simulated,
    )


def decode_ack(frame: Frame, expected_command: Command, *, expected_address: int | None = None) -> CommandAck:
    if frame.command != expected_command:
        raise ProtocolError(f"Expected {expected_command.name}, got {frame.command!r}")
    if expected_address is not None and frame.address != expected_address:
        raise ProtocolError(f"Unexpected address 0x{frame.address:02X}; expected 0x{expected_address:02X}")
    if not frame.data:
        raise ProtocolError("Acknowledgement response is missing status byte")

    status = frame.data[0]
    if status not in (AckStatus.SUCCESS, AckStatus.FAILURE):
        raise ProtocolError(f"Unknown acknowledgement status 0x{status:02X}")

    concentration: int | None = None
    if expected_command == Command.SET_CAL_GAS:
        if len(frame.data) != 3:
            raise ProtocolError("Set calibration gas acknowledgement must include status plus two-byte concentration")
        concentration = _u16(frame.data[1], frame.data[2])
    elif len(frame.data) != 1:
        raise ProtocolError(f"{expected_command.name} acknowledgement has unexpected data length {len(frame.data)}")

    return CommandAck(
        command=int(expected_command),
        address=frame.address,
        success=status == AckStatus.SUCCESS,
        status_code=status,
        concentration=concentration,
    )

