"""Command constants and command-frame builders."""

from __future__ import annotations

from enum import IntEnum

from .crc16 import modbus_crc16

START_BYTE = 0xAA
END_BYTE = 0xEE


class Command(IntEnum):
    READ_CONCENTRATION = 0x01
    ZERO = 0x02
    CALIBRATE = 0x03
    CHANGE_ADDRESS = 0x04
    SET_CAL_GAS = 0x05
    READ_INFO = 0x0F


class AckStatus(IntEnum):
    SUCCESS = 0x10
    FAILURE = 0x20


def build_frame(command: Command, *data: int) -> bytes:
    """Build a binary command frame, calculating CRC dynamically."""

    body = bytes((int(command), *[value & 0xFF for value in data]))
    return bytes((START_BYTE,)) + body + modbus_crc16(body) + bytes((END_BYTE,))


def read_info(address: int) -> bytes:
    return build_frame(Command.READ_INFO, address)


def read_concentration(address: int) -> bytes:
    return build_frame(Command.READ_CONCENTRATION, address)


def zero(address: int) -> bytes:
    return build_frame(Command.ZERO, address)


def calibrate(address: int) -> bytes:
    return build_frame(Command.CALIBRATE, address)


def change_address(new_address: int) -> bytes:
    # The PDF command contains only command 0x04 and the new address byte.
    return build_frame(Command.CHANGE_ADDRESS, new_address)


def set_calibration_gas(address: int, concentration: int) -> bytes:
    if not 0 <= concentration <= 0xFFFF:
        raise ValueError("Calibration gas concentration must fit in 16 bits")
    return build_frame(
        Command.SET_CAL_GAS,
        address,
        (concentration >> 8) & 0xFF,
        concentration & 0xFF,
    )

