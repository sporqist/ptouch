# SPDX-FileCopyrightText: 2026 Marius Alwan Meyer
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Check a print job against the raster command grammar before sending it.

A job that a printer misreads can feed tape until the cassette is empty,
and printers cannot be stopped over the network. ``validate_job`` parses
the bytes independently of how they were built and refuses anything
outside the grammar of Brother's raster command references, using the
printer model's own limits (bytes per raster line, margin range).

Per page: ``ESC i a 01``, then the control codes ``ESC i z``, ``ESC i M``,
``ESC i K``, ``ESC i d`` exactly once each and ``ESC i A`` at most once
(only with auto cut), then ``M`` (compression), raster lines, and ``0C``
(more pages follow) or ``1A`` (last page, feed). The invalidate and
initialize preamble is sent when the printer object is created and is
not part of a job.

Across pages: every page carries the same settings (print information
flags, media and width, ``ESC i M``, ``ESC i A``, ``ESC i K``,
``ESC i d`` and compression); a PT-E550W cuts fully after every label
when they change between pages. With cut-each N the job has a multiple
of N pages.

Printers with ``LEGACY_COMMANDS`` (PT-2730) get their own, smaller
grammar: ``ESC i R 01``, then ``ESC i M`` (not 0) at most once and
``ESC i K 08`` at most once (only with auto cut), before the first page
only; every page is uncompressed ``G`` lines (at least one) and ``0C`` or
``1A``. Any other command is refused: the PT-2730 hangs on the newer ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .packbits import decode

if TYPE_CHECKING:
    from .printer import LabelPrinter

# Bits each command may carry, from the raster references.
_PI_FLAGS = 0x02 | 0x04 | 0x08 | 0x40 | 0x80
_MODE_BITS = 0x40 | 0x80  # auto cut, mirror
_ADVANCED_BITS = (
    0x04 | 0x08 | 0x10 | 0x40 | 0x80
)  # half cut, no chain, special tape, high res, no buffer clear
_HIGH_RES = 0x40
_AUTO_CUT = 0x40
_ESC_I_SIZES = {b"z": 10, b"M": 1, b"A": 1, b"K": 1, b"d": 2}


class InvalidJobError(ValueError):
    """The job does not match the raster command grammar."""


@dataclass
class PageSummary:
    """What one page asks the printer to do."""

    raster_lines: int
    margin_dots: int
    auto_cut: bool
    half_cut: bool
    chain: bool
    high_resolution: bool
    compressed: bool
    last: bool
    cut_each: int | None = None


@dataclass
class JobSummary:
    """A validated job."""

    pages: list[PageSummary] = field(default_factory=list)

    @property
    def raster_lines(self) -> int:
        """Total raster lines over all pages."""
        return sum(p.raster_lines for p in self.pages)


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.i = 0

    def fail(self, msg: str) -> InvalidJobError:
        return InvalidJobError(f"byte {self.i}: {msg}")

    def take(self, n: int) -> bytes:
        if self.i + n > len(self.data):
            raise self.fail("job ends in the middle of a command")
        out = self.data[self.i : self.i + n]
        self.i += n
        return out

    def peek(self, n: int = 1) -> bytes:
        return self.data[self.i : self.i + n]


def _header(r: _Reader, page: int) -> dict[bytes, bytes]:
    """Read the ESC i control codes of one page (after ESC i a 01)."""
    if r.take(4) != b"\x1bia\x01":
        r.i -= 4
        raise r.fail(f"page {page}: expected ESC i a 01 (raster mode)")
    seen: dict[bytes, bytes] = {}
    while r.peek(2) == b"\x1bi":
        r.take(2)
        cmd = r.take(1)
        if cmd not in _ESC_I_SIZES:
            raise r.fail(f"page {page}: unexpected command ESC i {cmd!r}")
        if cmd in seen:
            raise r.fail(f"page {page}: ESC i {cmd.decode()} sent twice")
        seen[cmd] = r.take(_ESC_I_SIZES[cmd])
    for cmd in (b"z", b"M", b"K", b"d"):
        if cmd not in seen:
            raise r.fail(f"page {page}: ESC i {cmd.decode()} missing")
    return seen


def _check_print_information(r: _Reader, page: int, z: bytes) -> None:
    if z[0] & ~_PI_FLAGS:
        raise r.fail(f"page {page}: print information flags {z[0]:#04x} has undefined bits")
    if z[2] == 0:
        raise r.fail(f"page {page}: print information gives no media width")
    expected = 0 if page == 0 else 1
    if z[8] != expected:
        raise r.fail(f"page {page}: starting-page flag {z[8]} (expected {expected})")
    if z[9] != 0:
        raise r.fail(f"page {page}: print information byte n10 must be 0")


def _check_modes(r: _Reader, page: int, seen: dict[bytes, bytes]) -> None:
    mode, advanced = seen[b"M"][0], seen[b"K"][0]
    if mode & ~_MODE_BITS:
        raise r.fail(f"page {page}: various mode {mode:#04x} has undefined bits")
    if advanced & ~_ADVANCED_BITS:
        raise r.fail(f"page {page}: advanced mode {advanced:#04x} has undefined bits")
    if b"A" in seen:
        if not mode & _AUTO_CUT:
            raise r.fail(f"page {page}: cut-each (ESC i A) without auto cut")
        if not 1 <= seen[b"A"][0] <= 99:
            raise r.fail(f"page {page}: cut-each {seen[b'A'][0]} outside 1..99")


def _check_header(
    r: _Reader, page: int, seen: dict[bytes, bytes], printer: LabelPrinter
) -> PageSummary:
    z, mode, advanced = seen[b"z"], seen[b"M"][0], seen[b"K"][0]
    _check_print_information(r, page, z)
    _check_modes(r, page, seen)
    high_res = bool(advanced & _HIGH_RES)
    factor = 2 if high_res else 1
    margin = seen[b"d"][0] | seen[b"d"][1] << 8
    lo = printer._mm_to_dots(printer.MIN_MARGIN_MM) * factor
    hi = printer._mm_to_dots(printer.MAX_MARGIN_MM) * factor
    if not lo <= margin <= hi:
        raise r.fail(f"page {page}: margin {margin} dots outside {lo}..{hi}")
    return PageSummary(
        raster_lines=int.from_bytes(z[4:8], "little"),
        margin_dots=margin,
        auto_cut=bool(mode & _AUTO_CUT),
        half_cut=bool(advanced & 0x04),
        chain=not advanced & 0x08,
        high_resolution=high_res,
        compressed=False,
        last=False,
        cut_each=seen[b"A"][0] if b"A" in seen else None,
    )


def _raster_line(r: _Reader, page: int, compressed: bool, width: int) -> None:
    """Read one G or Z raster line at the reader's position."""
    if r.peek() == b"Z":
        if not compressed:
            raise r.fail(f"page {page}: zero raster line (Z) needs TIFF compression")
        r.take(1)
        return
    r.take(1)  # G
    n = int.from_bytes(r.take(2), "little")
    block = r.take(n)
    if not compressed:
        if n != width:
            raise r.fail(f"page {page}: uncompressed line of {n} bytes (expected {width})")
        return
    if n > width + 1:
        raise r.fail(f"page {page}: compressed line of {n} bytes (max {width + 1})")
    try:
        decoded = decode(block)
    except ValueError as e:
        raise r.fail(f"page {page}: broken PackBits data ({e})") from e
    if len(decoded) != width:
        raise r.fail(f"page {page}: raster line does not decode to {width} bytes")


def _raster(r: _Reader, page: int, compressed: bool, width: int) -> int:
    """Read raster lines up to the page terminator; return their count."""
    lines = 0
    while True:
        b = r.peek()
        if not b:
            raise r.fail(f"page {page}: job ends without a print command (0C or 1A)")
        if b in (b"\x0c", b"\x1a"):
            return lines
        if b not in (b"G", b"Z"):
            raise r.fail(f"page {page}: unexpected byte {b.hex()} in raster data")
        _raster_line(r, page, compressed, width)
        lines += 1


def _page(r: _Reader, page: int, printer: LabelPrinter) -> tuple[PageSummary, tuple[bytes, ...]]:
    """Read one page; return its summary and the settings that must not change."""
    seen = _header(r, page)
    info = _check_header(r, page, seen, printer)
    comp = r.take(2)
    if comp not in (b"M\x00", b"M\x02"):
        r.i -= 2
        raise r.fail(f"page {page}: expected compression M 00 or M 02")
    info.compressed = comp == b"M\x02"
    lines = _raster(r, page, info.compressed, printer.BYTES_PER_LINE)
    if lines != info.raster_lines:
        said = info.raster_lines
        raise r.fail(f"page {page}: {lines} raster lines sent, print information says {said}")
    info.last = r.take(1) == b"\x1a"
    z = seen[b"z"]
    settings = (z[:4], seen[b"M"], seen.get(b"A", b""), seen[b"K"], seen[b"d"], comp)
    return info, settings


def _check_cut_each_pages(summary: JobSummary) -> None:
    each = summary.pages[0].cut_each
    if each and len(summary.pages) % each:
        raise InvalidJobError(f"{len(summary.pages)} pages is not a multiple of cut-each {each}")


def _legacy_header(r: _Reader) -> tuple[int, int | None]:
    """Read a legacy job header; return ESC i M and ESC i K (or None)."""
    if r.take(4) != b"iR":
        r.i -= 4
        raise r.fail("page 0: expected ESC i R 01 (legacy raster mode)")
    mode = 0
    advanced: int | None = None
    if r.peek(3) == b"iM":
        r.take(3)
        mode = r.take(1)[0]
        if not mode or mode & ~_MODE_BITS:
            raise r.fail(f"page 0: various mode {mode:#04x} (expected 40h and/or 80h)")
    if r.peek(3) == b"iK":
        r.take(3)
        advanced = r.take(1)[0]
        if advanced != 0x08:
            raise r.fail(f"page 0: advanced mode {advanced:#04x} (only 08h is sent)")
        if not mode & _AUTO_CUT:
            raise r.fail("page 0: ESC i K 08 without auto cut")
    return mode, advanced


def _validate_legacy(data: bytes, printer: LabelPrinter, max_pages: int | None) -> JobSummary:
    """Validate a job for a ``LEGACY_COMMANDS`` printer (see module doc)."""
    r = _Reader(data)
    summary = JobSummary()
    mode, advanced = _legacy_header(r)
    while True:
        page = len(summary.pages)
        if max_pages is not None and page >= max_pages:
            raise r.fail(f"more than {max_pages} pages")
        if r.peek() not in (b"G", b"", b""):
            raise r.fail(f"page {page}: unexpected byte {r.peek().hex()} (only raster lines)")
        lines = _raster(r, page, False, printer.BYTES_PER_LINE)
        if not lines:
            raise r.fail(f"page {page}: no raster lines")
        last = r.take(1) == b""
        summary.pages.append(
            PageSummary(
                raster_lines=lines,
                margin_dots=0,
                auto_cut=bool(mode & _AUTO_CUT),
                half_cut=False,
                chain=advanced is None,
                high_resolution=False,
                compressed=False,
                last=last,
            )
        )
        if last:
            if r.i < len(data):
                raise r.fail("data after the last page (1A)")
            return summary
        if r.i >= len(data):
            raise r.fail(f"page {page}: job ends after 0C, without 1A")


def validate_job(data: bytes, printer: LabelPrinter, max_pages: int | None = None) -> JobSummary:
    """Validate a job built for ``printer``.

    Parameters
    ----------
    data : bytes
        The job as it would be written to the connection.
    printer : LabelPrinter
        The printer model the job is for (bytes per line, margin limits).
    max_pages : int or None, optional
        Refuse jobs with more pages (labels) than this.

    Returns
    -------
    JobSummary
        One summary per page.

    Raises
    ------
    InvalidJobError
        At the first byte that does not fit the grammar.
    """
    if printer.LEGACY_COMMANDS:
        if not data:
            raise InvalidJobError("empty job")
        return _validate_legacy(data, printer, max_pages)
    r = _Reader(data)
    summary = JobSummary()
    first: tuple[bytes, ...] | None = None
    while r.i < len(data):
        page = len(summary.pages)
        if max_pages is not None and page >= max_pages:
            raise r.fail(f"more than {max_pages} pages")
        start = r.i
        info, settings = _page(r, page, printer)
        if first is None:
            first = settings
        elif settings != first:
            raise InvalidJobError(
                f"byte {start}: page {page}: settings differ from page 0 "
                "(cut, mode, margin and compression must be the same on every page)"
            )
        summary.pages.append(info)
        if info.last and r.i < len(data):
            raise r.fail("data after the last page (1A)")
    if not summary.pages:
        raise InvalidJobError("empty job")
    _check_cut_each_pages(summary)
    return summary
