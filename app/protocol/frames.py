"""Frame data models for validated 4SMART-C01 packets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .commands import Command


class FrameError(str, Enum):
    GARBAGE = "garbage"
    MALFORMED = "malformed"
    CRC = "crc_error"


@dataclass(frozen=True)
class Frame:
    raw: bytes
    command: Command | int
    address: int
    data: bytes


@dataclass(frozen=True)
class ParseEvent:
    raw: bytes
    frame: Frame | None = None
    error: FrameError | None = None
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.frame is not None and self.error is None


def hex_bytes(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)

