from datetime import datetime

import pytest

from app.protocol.decoder import ProtocolError, decode_gas_reading, decode_module_info
from app.protocol.parser import FrameParser


def parse_one(hex_text: str):
    events = FrameParser().feed(bytes.fromhex(hex_text))
    assert len(events) == 1
    assert events[0].ok
    return events[0].frame


def test_module_info_parser_pdf_example() -> None:
    frame = parse_one("AA 0F 01 0F 00 14 00 05 00 02 00 01 02 C5 99 EE")
    info = decode_module_info(frame)
    assert info.address == 0x01
    assert info.sensor_type_code == 0x0F
    assert info.sensor_type_name == "PH3"
    assert info.measurement_range == 20
    assert info.calibration_concentration == 5
    assert info.high_alarm == 2
    assert info.low_alarm == 1
    assert info.unit_code == 0x02
    assert info.unit_name == "ppm"


def test_concentration_positive_integer() -> None:
    frame = parse_one("AA 01 01 00 00 01 00 3D 9A EE")
    reading = decode_gas_reading(frame, expected_address=0x01, unit="ppm", timestamp=datetime(2026, 8, 17))
    assert reading.value == 1.0


def test_concentration_positive_fractional_value() -> None:
    frame = parse_one("AA 01 01 00 00 01 25 FC 41 EE")
    reading = decode_gas_reading(frame, expected_address=0x01, unit="ppm")
    assert reading.value == 1.37


def test_concentration_negative_value() -> None:
    frame = parse_one("AA 01 01 80 00 02 32 95 7F EE")
    reading = decode_gas_reading(frame, expected_address=0x01, unit="ppm")
    assert reading.value == -2.5


def test_concentration_maximum_integer_field() -> None:
    frame = parse_one("AA 01 01 00 FF FF 3F 0D DA EE")
    reading = decode_gas_reading(frame, expected_address=0x01, unit="ppm")
    assert reading.value == 65535.63


def test_crc_failure_rejected_by_parser() -> None:
    events = FrameParser().feed(bytes.fromhex("AA 01 01 00 00 01 25 00 00 EE"))
    assert not events[0].ok


def test_truncated_message_waits_for_more_bytes() -> None:
    parser = FrameParser()
    assert parser.feed(bytes.fromhex("AA 01 01 00")) == []


def test_wrong_address_rejected_by_decoder() -> None:
    frame = parse_one("AA 01 02 00 00 01 25 B8 41 EE")
    with pytest.raises(ProtocolError):
        decode_gas_reading(frame, expected_address=0x01, unit="ppm")
