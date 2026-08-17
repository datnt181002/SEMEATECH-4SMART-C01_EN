from app.protocol import commands


def test_command_builders_match_pdf_examples() -> None:
    assert commands.read_info(0x01) == bytes.fromhex("AA 0F 01 C5 80 EE")
    assert commands.read_concentration(0x01) == bytes.fromhex("AA 01 01 C1 E0 EE")
    assert commands.zero(0x01) == bytes.fromhex("AA 02 01 C1 10 EE")
    assert commands.calibrate(0x01) == bytes.fromhex("AA 03 01 C0 80 EE")
    assert commands.change_address(0x02) == bytes.fromhex("AA 04 02 82 B1 EE")
    assert commands.set_calibration_gas(0x01, 500) == bytes.fromhex("AA 05 01 01 F4 51 3F EE")


def test_set_calibration_gas_rejects_out_of_range() -> None:
    try:
        commands.set_calibration_gas(0x01, 0x10000)
    except ValueError:
        return
    raise AssertionError("Expected ValueError")

