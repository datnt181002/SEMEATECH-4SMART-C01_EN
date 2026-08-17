from app.protocol.crc16 import modbus_crc16


def test_pdf_crc_examples() -> None:
    examples = {
        bytes.fromhex("0F 01"): bytes.fromhex("C5 80"),
        bytes.fromhex("01 01"): bytes.fromhex("C1 E0"),
        bytes.fromhex("02 01"): bytes.fromhex("C1 10"),
        bytes.fromhex("03 01"): bytes.fromhex("C0 80"),
        bytes.fromhex("04 02"): bytes.fromhex("82 B1"),
        bytes.fromhex("05 01 01 F4"): bytes.fromhex("51 3F"),
    }
    for payload, expected in examples.items():
        assert modbus_crc16(payload) == expected

