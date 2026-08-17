from app.protocol.commands import read_concentration
from app.protocol.frames import FrameError
from app.protocol.parser import FrameParser


GOOD = bytes.fromhex("AA 01 01 00 00 01 25 FC 41 EE")
BAD_CRC = bytes.fromhex("AA 01 01 00 00 01 25 00 00 EE")


def test_parser_recovers_from_garbage_before_valid_packet() -> None:
    parser = FrameParser()
    events = parser.feed(b"\x00\xFF" + read_concentration(0x01))
    assert events[0].error == FrameError.GARBAGE
    assert events[1].ok


def test_parser_combines_half_packets() -> None:
    parser = FrameParser()
    assert parser.feed(GOOD[:4]) == []
    events = parser.feed(GOOD[4:])
    assert len(events) == 1
    assert events[0].ok


def test_parser_extracts_two_packets_from_one_read() -> None:
    parser = FrameParser()
    events = parser.feed(GOOD + GOOD)
    assert [event.ok for event in events] == [True, True]


def test_parser_reports_bad_packet_and_recovers_for_good_packet() -> None:
    parser = FrameParser()
    events = parser.feed(BAD_CRC + GOOD)
    assert events[0].error == FrameError.CRC
    assert events[1].ok
