"""CRC16/MODBUS implementation used by the 4SMART-C01 protocol."""

from __future__ import annotations


def modbus_crc16(data: bytes) -> bytes:
    """Return the CRC bytes in the byte order documented by the module.

    Appendix 1 starts with 0xFFFF, uses polynomial 0xA001, then transmits the
    low CRC byte first. Example from the PDF: 05 01 01 F4 -> 51 3F.
    """

    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
            crc &= 0xFFFF
    return bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def verify_crc(payload_with_crc: bytes) -> bool:
    """Validate bytes containing protocol data followed by two CRC bytes."""

    if len(payload_with_crc) < 3:
        return False
    return modbus_crc16(payload_with_crc[:-2]) == payload_with_crc[-2:]

