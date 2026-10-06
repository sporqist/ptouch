# SPDX-FileCopyrightText: 2026 Marius Alwan Meyer
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for the built-in PackBits encoder."""

import random

import pytest

from ptouch.packbits import decode, encode, encode_raster_line


def test_reference_example() -> None:
    """The worked example from Brother's raster command reference."""
    data = bytes(20) + bytes([0x22, 0x22]) + bytes([0x23, 0xBA, 0xBF, 0xA2, 0x22, 0x2B])
    assert encode(data) == bytes.fromhex("ED00FF220523BABFA2222B")


@pytest.mark.parametrize(
    "data",
    [b"", b"\x00", b"\x00" * 16, b"\xab" * 300, bytes(range(256)), bytes(range(200)) * 2],
)
def test_round_trip_edge_cases(data: bytes) -> None:
    """Encoding then decoding gives the input back."""
    assert decode(encode(data)) == data


def test_round_trip_random() -> None:
    """Random raster-like lines survive a round trip."""
    rng = random.Random(1)
    for _ in range(5000):
        line = bytes(rng.choice([0x00, 0xFF, rng.randrange(256)]) for _ in range(16))
        assert decode(encode(line)) == line
        assert decode(encode_raster_line(line)) == line


def test_runs_capped_at_128() -> None:
    """No run or literal header covers more than 128 bytes."""
    enc = encode(b"\x11" * 300)
    assert enc == bytes([257 - 128, 0x11, 257 - 128, 0x11, 257 - 44, 0x11])
    enc = encode(bytes(range(256)) * 2)
    assert enc[0] == 127 and enc[129] == 127


def test_raster_line_never_exceeds_17_bytes() -> None:
    """Lines whose compression exceeds 16 bytes become one literal run."""
    worst = bytes([0, 0, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8])
    assert len(encode(worst)) > 16
    assert encode_raster_line(worst) == b"\x0f" + worst
    rng = random.Random(2)
    for _ in range(5000):
        line = bytes(rng.choice([0x00, 0xFF, rng.randrange(256)]) for _ in range(16))
        assert len(encode_raster_line(line)) <= 17


def test_raster_line_compresses_when_shorter() -> None:
    """Lines that compress to 16 bytes or less stay compressed."""
    assert encode_raster_line(b"\xff" * 16) == bytes([257 - 16, 0xFF])


def test_decode_rejects_truncated() -> None:
    """Truncated data raises instead of silently producing short lines."""
    with pytest.raises(ValueError):
        decode(b"\x05\x01\x02")
    with pytest.raises(ValueError):
        decode(b"\xff")
