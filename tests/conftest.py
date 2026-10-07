# SPDX-FileCopyrightText: 2024-2026 Nicolai Buchwitz <nb@tipi-net.de>
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared test fixtures for ptouch tests."""

import pytest
from PIL import Image

from ptouch import (
    Tape6mm,
    Tape12mm,
    Tape24mm,
    Tape36mm,
)
from ptouch.connection import Connection
from ptouch.packbits import decode


class MockConnection(Connection):
    """Mock connection that captures data sent to the printer."""

    def __init__(self) -> None:
        self.data: bytes = b""
        self.closed = False
        self.connected = False

    def connect(self, printer: object) -> None:
        """Mock connect - just mark as connected."""
        del printer  # unused
        self.connected = True

    def write(self, payload: bytes) -> None:
        """Capture data instead of sending it."""
        self.data += payload

    def close(self) -> None:
        """Mark connection as closed."""
        self.closed = True


@pytest.fixture
def mock_connection() -> MockConnection:
    """Provide a mock connection for testing."""
    return MockConnection()


@pytest.fixture
def sample_image() -> Image.Image:
    """Create a simple test image."""
    img = Image.new("RGB", (100, 50), color=(255, 255, 255))
    return img


@pytest.fixture
def sample_image_with_content() -> Image.Image:
    """Create a test image with some black content."""
    img = Image.new("RGB", (100, 50), color=(255, 255, 255))
    # Draw a black rectangle in the center
    for x in range(25, 75):
        for y in range(10, 40):
            img.putpixel((x, y), (0, 0, 0))
    return img


@pytest.fixture
def tape_6mm() -> Tape6mm:
    """Provide a 6mm tape instance."""
    return Tape6mm()


@pytest.fixture
def tape_12mm() -> Tape12mm:
    """Provide a 12mm tape instance."""
    return Tape12mm()


@pytest.fixture
def tape_24mm() -> Tape24mm:
    """Provide a 24mm tape instance."""
    return Tape24mm()


@pytest.fixture
def tape_36mm() -> Tape36mm:
    """Provide a 36mm tape instance."""
    return Tape36mm()


# ---- reading a print job back as a list of commands ------------------------

_ESC_I_SIZES = {b"a": 1, b"z": 10, b"M": 1, b"A": 1, b"K": 1, b"d": 2}


def _raster_run(data: bytes, i: int, compressed: bool) -> tuple[int, int, int]:
    """Consume raster lines from i; return (next index, lines, longest block)."""
    lines = longest = 0
    while i < len(data) and data[i] in (0x47, 0x5A):
        if data[i] == 0x5A:
            i += 1
        else:
            n = data[i + 1] | data[i + 2] << 8
            block = data[i + 3 : i + 3 + n]
            width = len(decode(block)) if compressed else len(block)
            assert width == 16, f"bad raster line at {i}"
            longest = max(longest, n)
            i += 3 + n
        lines += 1
    return i, lines, longest


def _one_command(data: bytes, i: int, compressed: bool) -> tuple[int, tuple[str, str]]:
    """Parse the command at i; return (next index, (name, value))."""
    if data[i] == 0x00:
        j = i
        while j < len(data) and data[j] == 0x00:
            j += 1
        return j, ("invalidate", f"{j - i} x 00")
    if data[i : i + 2] == b"\x1b@":
        return i + 2, ("initialize", "1b 40")
    if data[i : i + 2] == b"\x1bi":
        n = _ESC_I_SIZES[data[i + 2 : i + 3]]
        return i + 3 + n, ("ESC i " + chr(data[i + 2]), data[i + 3 : i + 3 + n].hex(" "))
    if data[i] == 0x4D:
        return i + 2, ("compression", f"{data[i + 1]:02x}")
    if data[i] in (0x47, 0x5A):
        j, lines, longest = _raster_run(data, i, compressed)
        if not compressed:
            return j, ("raster", f"{lines} lines, uncompressed")
        size = "all blocks <= 17 bytes" if longest <= 17 else f"a block of {longest} bytes"
        return j, ("raster", f"{lines} lines, {size}")
    if data[i] in (0x0C, 0x1A):
        return i + 1, ("print" if data[i] == 0x0C else "print + feed", f"{data[i]:02x}")
    raise AssertionError(f"unexpected byte {data[i]:#04x} at {i}")


def job_commands(data: bytes) -> list[tuple[str, str]]:
    """Read a raster print job back as readable (command, value) pairs.

    Raster lines between two commands are summarised as one entry; they
    are read as PackBits after ``M 02`` and as plain 16-byte lines after
    ``M 00``.
    """
    out: list[tuple[str, str]] = []
    i = 0
    compressed = True
    while i < len(data):
        i, cmd = _one_command(data, i, compressed)
        if cmd[0] == "compression":
            compressed = cmd[1] == "02"
        out.append(cmd)
    return out
