"""Streaming parser that recovers synchronized 4SMART-C01 frames."""

from __future__ import annotations

from .commands import END_BYTE, START_BYTE, Command
from .crc16 import modbus_crc16
from .frames import Frame, FrameError, ParseEvent

MIN_FRAME_LENGTH = 6
MAX_FRAME_LENGTH = 64


class FrameParser:
    """Incrementally parse a byte stream into CRC-checked frames."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    @property
    def buffered(self) -> bytes:
        return bytes(self._buffer)

    def reset(self) -> None:
        self._buffer.clear()

    def feed(self, chunk: bytes) -> list[ParseEvent]:
        self._buffer.extend(chunk)
        events: list[ParseEvent] = []

        while self._buffer:
            start = self._find_start()
            if start is None:
                garbage = bytes(self._buffer)
                self._buffer.clear()
                events.append(ParseEvent(raw=garbage, error=FrameError.GARBAGE, message="Discarded bytes before start byte"))
                break
            if start > 0:
                garbage = bytes(self._buffer[:start])
                del self._buffer[:start]
                events.append(ParseEvent(raw=garbage, error=FrameError.GARBAGE, message="Discarded bytes before start byte"))

            end_index = self._find_end_after_start()
            if end_index is None:
                if len(self._buffer) > MAX_FRAME_LENGTH:
                    bad = bytes(self._buffer[:1])
                    del self._buffer[:1]
                    events.append(ParseEvent(raw=bad, error=FrameError.MALFORMED, message="Frame exceeded maximum length"))
                    continue
                break

            candidate = bytes(self._buffer[: end_index + 1])
            del self._buffer[: end_index + 1]
            events.append(self._parse_candidate(candidate))

        return events

    def _find_start(self) -> int | None:
        try:
            return self._buffer.index(START_BYTE)
        except ValueError:
            return None

    def _find_end_after_start(self) -> int | None:
        try:
            return self._buffer.index(END_BYTE, 1)
        except ValueError:
            return None

    def _parse_candidate(self, raw: bytes) -> ParseEvent:
        if len(raw) < MIN_FRAME_LENGTH:
            return ParseEvent(raw=raw, error=FrameError.MALFORMED, message="Frame too short")
        if raw[0] != START_BYTE or raw[-1] != END_BYTE:
            return ParseEvent(raw=raw, error=FrameError.MALFORMED, message="Invalid frame boundary")

        body = raw[1:-3]
        received_crc = raw[-3:-1]
        expected_crc = modbus_crc16(body)
        if received_crc != expected_crc:
            return ParseEvent(raw=raw, error=FrameError.CRC, message=f"CRC mismatch: expected {expected_crc.hex(' ').upper()}")

        command_value = raw[1]
        try:
            command: Command | int = Command(command_value)
        except ValueError:
            command = command_value
        frame = Frame(raw=raw, command=command, address=raw[2], data=raw[3:-3])
        return ParseEvent(raw=raw, frame=frame)

