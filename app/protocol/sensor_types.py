"""Sensor type and unit lookup tables copied from 4SMART-C01_EN V1.4."""

from __future__ import annotations

from enum import IntEnum

SENSOR_TYPES: dict[int, str] = {
    0x01: "EX",
    0x02: "CO",
    0x03: "O2",
    0x04: "H2",
    0x05: "CH4",
    0x06: "C3H8",
    0x07: "CO2",
    0x08: "O3",
    0x09: "H2S",
    0x0A: "SO2",
    0x0B: "NH3",
    0x0C: "CL2",
    0x0D: "ETO",
    0x0E: "HCL",
    0x0F: "PH3",
    0x10: "HBr",
    0x11: "HCN",
    0x12: "AsH3",
    0x13: "HF",
    0x14: "Br2",
    0x15: "NO",
    0x16: "NO2",
    0x17: "NOX",
    0x18: "CLO2",
    0x19: "SiH4",
    0x1A: "None",
    0x1B: "None",
    0x1C: "None",
    0x1D: "None",
    0x1E: "None",
    0x1F: "THT",
    0x20: "C2H2",
    0x21: "C2H4",
    0x22: "CH2O",
    0x23: "None",
    0x24: "None",
    0x25: "C6H6",
    0x26: "H2O2",
    0x27: "C2H3CL",
    0x28: "VOC",
    0x29: "CH3SH",
    0x2A: "C4H8",
}


class UnitCode(IntEnum):
    PERCENT_LEL = 0x00
    PERCENT_VOL = 0x01
    PPM = 0x02
    PPB = 0x03
    NA = 0x04


UNITS: dict[int, str] = {
    UnitCode.PERCENT_LEL: "%LEL",
    UnitCode.PERCENT_VOL: "%VOL",
    UnitCode.PPM: "ppm",
    UnitCode.PPB: "ppb",
    UnitCode.NA: "N/A",
}


def sensor_name(code: int) -> str:
    return SENSOR_TYPES.get(code, f"Unknown (0x{code:02X})")


def unit_name(code: int) -> str:
    return UNITS.get(code, f"Unknown (0x{code:02X})")

