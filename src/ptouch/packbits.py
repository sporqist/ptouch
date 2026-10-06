# SPDX-FileCopyrightText: 2026 Marius Alwan Meyer
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""TIFF PackBits encoding for P-touch raster lines.

Replaces the third-party ``packbits`` package and adds the rule from
Brother's raster command reference (``M`` select compression mode,
"TIFF (Pack Bits)"): if compressing a raster line results in more than
16 bytes, the line is sent as all-different data, i.e. one literal run
of 17 bytes including the length byte.
"""

MAX_RUN = 128


def encode(data: bytes) -> bytes:
    """Encode bytes with PackBits.

    Two or more equal bytes become a repeat run (count byte ``257 - n``),
    everything else literal runs (count byte ``n - 1``), as in the
    reference's example: twenty ``00h`` -> ``ED 00``, two ``22h`` ->
    ``FF 22``.

    Parameters
    ----------
    data : bytes
        Uncompressed data.

    Returns
    -------
    bytes
        PackBits-encoded data.
    """
    out = bytearray()
    literal = bytearray()
    i = 0
    n = len(data)

    def flush_literal() -> None:
        while literal:
            chunk = literal[:MAX_RUN]
            out.append(len(chunk) - 1)
            out.extend(chunk)
            del literal[:MAX_RUN]

    while i < n:
        run = 1
        while i + run < n and run < MAX_RUN and data[i + run] == data[i]:
            run += 1
        if run >= 2:
            flush_literal()
            out.append(257 - run)
            out.append(data[i])
        else:
            literal.append(data[i])
        i += run
    flush_literal()
    return bytes(out)


def decode(data: bytes) -> bytes:
    """Decode PackBits data (the inverse of :func:`encode`).

    Parameters
    ----------
    data : bytes
        PackBits-encoded data.

    Returns
    -------
    bytes
        Decoded data.

    Raises
    ------
    ValueError
        If the data is truncated.
    """
    out = bytearray()
    i = 0
    while i < len(data):
        header = data[i]
        i += 1
        if header < 128:
            count = header + 1
            if i + count > len(data):
                raise ValueError("truncated literal run")
            out.extend(data[i : i + count])
            i += count
        elif header > 128:
            if i >= len(data):
                raise ValueError("truncated repeat run")
            out.extend(data[i : i + 1] * (257 - header))
            i += 1
        # 128 (0x80) is a no-op in PackBits
    return bytes(out)


def encode_raster_line(line: bytes) -> bytes:
    """Encode one raster line for the ``G`` (raster graphics transfer) command.

    Compressed data longer than 16 bytes is replaced by one literal run of
    the whole line, as the raster command reference requires.

    Parameters
    ----------
    line : bytes
        One uncompressed raster line (16 bytes for 128-pin heads).

    Returns
    -------
    bytes
        Encoded line, at most ``len(line) + 1`` bytes.
    """
    encoded = encode(line)
    if len(encoded) > 16:
        return bytes([len(line) - 1]) + line
    return encoded
