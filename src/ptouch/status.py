# SPDX-FileCopyrightText: 2026 Marius Alwan Meyer
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""The printer's 32-byte status block.

Layout and values from Brother's raster command reference (PT-E550W/
P750W/P710BT, "Status information request", tables 1-9). The same block
is what ``ESC i S`` returns over USB and what network models publish
over SNMP (see :mod:`ptouch.snmp`).
"""

from dataclasses import dataclass
from enum import IntEnum, IntFlag

STATUS_LENGTH = 32


class StatusError(ValueError):
    """The bytes are not a printer status block."""


class Error1(IntFlag):
    """Error information 1 (offset 8)."""

    NO_MEDIA = 0x01
    CUTTER_JAM = 0x04
    WEAK_BATTERIES = 0x08
    HIGH_VOLTAGE_ADAPTER = 0x40


class Error2(IntFlag):
    """Error information 2 (offset 9)."""

    WRONG_MEDIA = 0x01
    COVER_OPEN = 0x10
    OVERHEATING = 0x20


class StatusType(IntEnum):
    """Status type (offset 18)."""

    REPLY = 0x00
    PRINTING_COMPLETED = 0x01
    ERROR = 0x02
    TURNED_OFF = 0x04
    NOTIFICATION = 0x05
    PHASE_CHANGE = 0x06


class PhaseType(IntEnum):
    """Phase type (offset 19)."""

    EDITING = 0x00  # reception possible
    PRINTING = 0x01


TAPE_COLORS = {
    0x01: "white", 0x02: "other", 0x03: "clear", 0x04: "red", 0x05: "blue",
    0x06: "yellow", 0x07: "green", 0x08: "black", 0x09: "clear (white text)",
    0x20: "matte white", 0x21: "matte clear", 0x22: "matte silver",
    0x23: "satin gold", 0x24: "satin silver", 0x30: "blue (D)", 0x31: "red (D)",
    0x40: "fluorescent orange", 0x41: "fluorescent yellow",
    0x50: "berry pink (S)", 0x51: "light gray (S)", 0x52: "lime green (S)",
    0x60: "yellow (F)", 0x61: "pink (F)", 0x62: "blue (F)",
    0x70: "white (heat-shrink tube)", 0x90: "white (flexible ID)",
    0x91: "yellow (flexible ID)", 0xF0: "cleaning", 0xF1: "stencil", 0xFF: "incompatible",
}  # fmt: skip

TEXT_COLORS = {
    0x01: "white", 0x02: "other", 0x04: "red", 0x05: "blue", 0x08: "black",
    0x0A: "gold", 0x62: "blue (F)", 0xF0: "cleaning", 0xF1: "stencil", 0xFF: "incompatible",
}  # fmt: skip

MEDIA_TYPES = {
    0x00: "no media", 0x01: "laminated tape", 0x03: "non-laminated tape",
    0x11: "heat-shrink tube 2:1", 0x17: "heat-shrink tube 3:1", 0xFF: "incompatible tape",
}  # fmt: skip

# 63h: read from a PT-2730 on 2026-10-07 (not in a Brother reference).
MODEL_CODES = {0x63: "PT-2730", 0x66: "PT-E550W", 0x68: "PT-P750W"}


@dataclass(frozen=True)
class PrinterStatus:
    """A decoded status block."""

    raw: bytes
    model_code: int
    error1: Error1
    error2: Error2
    media_width_mm: int
    media_type: int
    mode: int
    media_length_mm: int
    status_type: int
    phase_type: int
    phase_number: int
    notification: int
    tape_color: int
    text_color: int

    @property
    def model(self) -> str:
        """Model name if the reference lists the code, else the code in hex."""
        return MODEL_CODES.get(self.model_code, f"model {self.model_code:#04x}")

    @property
    def has_error(self) -> bool:
        """Any error bit set, or an error status reported."""
        return bool(self.error1 or self.error2) or self.status_type == StatusType.ERROR

    @property
    def errors(self) -> list[str]:
        """Readable names of the error bits that are set."""
        names = [f.name for f in Error1 if f in self.error1]
        names += [f.name for f in Error2 if f in self.error2]
        return [n.lower().replace("_", " ") for n in names if n]

    @property
    def is_printing(self) -> bool:
        """The printer reports the printing phase."""
        return self.phase_type == PhaseType.PRINTING

    @property
    def has_media(self) -> bool:
        """A cassette is loaded and recognised."""
        return self.media_type != 0x00 and self.media_width_mm != 0

    @property
    def tape(self) -> str:
        """E.g. ``24 mm laminated tape, black on white``."""
        if not self.has_media:
            return "no tape"
        media = MEDIA_TYPES.get(self.media_type, f"media {self.media_type:#04x}")
        tape = TAPE_COLORS.get(self.tape_color, f"tape {self.tape_color:#04x}")
        text = TEXT_COLORS.get(self.text_color, f"ink {self.text_color:#04x}")
        return f"{self.media_width_mm} mm {media}, {text} on {tape}"


def parse_status(data: bytes) -> PrinterStatus:
    """Decode a 32-byte status block.

    Parameters
    ----------
    data : bytes
        The block as read from the printer.

    Returns
    -------
    PrinterStatus
        The decoded fields.

    Raises
    ------
    StatusError
        If the bytes are not a status block (wrong length or header).
    """
    if len(data) != STATUS_LENGTH:
        raise StatusError(f"status block must be {STATUS_LENGTH} bytes, got {len(data)}")
    if data[0] != 0x80 or data[1] != 0x20 or data[2] != 0x42:
        raise StatusError(f"not a status block (header {data[:3].hex(' ')})")
    return PrinterStatus(
        raw=bytes(data),
        model_code=data[4],
        error1=Error1(data[8] & sum(Error1)),
        error2=Error2(data[9] & sum(Error2)),
        media_width_mm=data[10],
        media_type=data[11],
        mode=data[15],
        media_length_mm=data[17],
        status_type=data[18],
        phase_type=data[19],
        phase_number=(data[20] << 8) | data[21],
        notification=data[22],
        tape_color=data[24],
        text_color=data[25],
    )
