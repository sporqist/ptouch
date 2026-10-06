# SPDX-FileCopyrightText: 2026 Marius Alwan Meyer
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for validate_job and the validated send path."""

import pytest
from PIL import Image

from ptouch import PTE550W, PTP900, Label, Tape24mm
from ptouch.validate import InvalidJobError, validate_job

from .conftest import MockConnection


def _label(width: int = 40) -> Label:
    image = Image.new("RGB", (width, 128), "white")
    for x in range(0, width, 3):
        for y in range(0, 128, 2):
            image.putpixel((x, y), (0, 0, 0))
    return Label(image, Tape24mm)


def _job(printer_cls: type = PTE550W, labels: int = 1) -> tuple[bytes, object]:
    conn = MockConnection()
    printer = printer_cls(conn)
    pages = [
        printer.build_page(_label(), feed=i == labels - 1, first_page=i == 0) for i in range(labels)
    ]
    return b"".join(pages), printer


class TestAccepts:
    """Jobs the library builds are valid for their model."""

    @pytest.mark.parametrize("printer_cls", [PTE550W, PTP900])
    @pytest.mark.parametrize("labels", [1, 3])
    def test_built_jobs_validate(self, printer_cls: type, labels: int) -> None:
        """Single labels and strips, for a 128-pin and a 560-pin model."""
        data, printer = _job(printer_cls, labels)
        summary = validate_job(data, printer)  # type: ignore[arg-type]
        assert len(summary.pages) == labels
        assert summary.pages[-1].last and all(not p.last for p in summary.pages[:-1])
        assert all(p.raster_lines == 40 for p in summary.pages)

    def test_uncompressed_jobs_validate(self) -> None:
        """Compression off: raster lines are plain full-width blocks."""
        conn = MockConnection()
        printer = PTE550W(conn, use_compression=False)
        summary = validate_job(printer.build_page(_label()), printer)
        assert not summary.pages[0].compressed


class TestRejects:
    """Anything outside the grammar is refused with the byte position."""

    def _bad(self, mutate: object, labels: int = 1, max_pages: int | None = None) -> str:
        data, printer = _job(PTE550W, labels)
        bad = mutate(data)  # type: ignore[operator]
        with pytest.raises(InvalidJobError) as e:
            validate_job(bad, printer, max_pages=max_pages)  # type: ignore[arg-type]
        return str(e.value)

    def test_margin_below_minimum(self) -> None:
        """The failed job of 2026-10-06 used 11 dots; the minimum is 14."""
        msg = self._bad(lambda d: d.replace(b"\x1bid\x0e\x00", b"\x1bid\x0b\x00"))
        assert "margin 11 dots" in msg

    def test_cut_each_without_auto_cut(self) -> None:
        """ESC i A only makes sense with auto cut on."""
        msg = self._bad(lambda d: d.replace(b"\x1biM\x40", b"\x1biM\x00"))
        assert "without auto cut" in msg

    def test_raster_count_mismatch(self) -> None:
        """The print information must announce the lines that follow."""
        msg = self._bad(
            lambda d: d.replace(b"\x28\x00\x00\x00\x00\x00", b"\x29\x00\x00\x00\x00\x00")
        )
        assert "raster lines sent" in msg

    def test_missing_raster_mode_on_later_page(self) -> None:
        """Every page starts with ESC i a 01."""

        def drop_second(d: bytes) -> bytes:
            i = d.index(b"\x1bia\x01", d.index(b"\x1bia\x01") + 1)
            return d[:i] + d[i + 4 :]

        assert "ESC i a 01" in self._bad(drop_second, labels=2)

    def test_wrong_page_flag(self) -> None:
        """Later pages must carry n9 = 1."""

        def first_flag_everywhere(d: bytes) -> bytes:
            return d.replace(b"\x00\x00\x01\x00\x1biM", b"\x00\x00\x00\x00\x1biM")

        assert "starting-page flag" in self._bad(first_flag_everywhere, labels=2)

    def test_oversized_compressed_line(self) -> None:
        """A compressed raster line may not exceed 17 bytes (16-byte head)."""
        line = bytes(range(16))
        block = b"G" + (18).to_bytes(2, "little") + b"\x10" + line + b"\x00"

        def swap_first_line(d: bytes) -> bytes:
            i = d.index(b"M\x02") + 2
            j = d.index(b"G", i)
            n = int.from_bytes(d[j + 1 : j + 3], "little")
            return d[:j] + block + d[j + 3 + n :]

        assert "compressed line of 18 bytes" in self._bad(swap_first_line)

    def test_data_after_last_page(self) -> None:
        """Nothing may follow the final 1A."""
        assert "after the last page" in self._bad(lambda d: d + b"\x1bia\x01")

    def test_truncated_job(self) -> None:
        """A job cut off mid-way is refused."""
        assert "ends" in self._bad(lambda d: d[:-30])

    def test_unknown_command(self) -> None:
        """Commands outside the raster grammar are refused."""
        msg = self._bad(lambda d: d.replace(b"\x1biK", b"\x1biU\x00\x1biK", 1))
        assert "unexpected command" in msg

    def test_max_pages(self) -> None:
        """A page limit caps runaway job sizes."""
        assert "more than 2 pages" in self._bad(lambda d: d, labels=3, max_pages=2)


class TestSendJob:
    """print() and print_multi() validate before writing."""

    def test_invalid_job_is_not_sent(self) -> None:
        """Nothing reaches the connection when validation fails."""
        conn = MockConnection()
        printer = PTE550W(conn)
        before = len(conn.data)
        bad = printer.build_page(_label()).replace(b"\x1bid\x0e\x00", b"\x1bid\x0b\x00")
        with pytest.raises(InvalidJobError):
            printer.send_job(bad)
        assert len(conn.data) == before

    def test_print_multi_writes_once(self) -> None:
        """A strip goes out as one write after validation."""
        conn = MockConnection()
        printer = PTE550W(conn)
        writes: list[bytes] = []
        original = conn.write
        conn.write = lambda payload: (writes.append(payload), original(payload))[1]  # type: ignore[method-assign]
        printer.print_multi([_label(), _label(), _label()])
        assert len(writes) == 1
        assert len(validate_job(writes[0], printer).pages) == 3

    def test_max_pages_on_printer(self) -> None:
        """printer.max_pages limits print_multi()."""
        conn = MockConnection()
        printer = PTE550W(conn)
        printer.max_pages = 2
        with pytest.raises(InvalidJobError):
            printer.print_multi([_label(), _label(), _label()])


class TestSameSettingsOnEveryPage:
    """Changing cut settings between pages makes a PT-E550W cut after every label."""

    def _strip(self, labels: int = 3, **kw: object) -> tuple[bytes, PTE550W]:
        printer = PTE550W(MockConnection())
        return printer.build_job([_label() for _ in range(labels)], **kw), printer  # type: ignore[arg-type]

    def test_built_job_validates(self) -> None:
        """build_job gives every page the same settings."""
        data, printer = self._strip(4, cut_each=2, half_cut=True)
        summary = validate_job(data, printer)
        assert [p.cut_each for p in summary.pages] == [2, 2, 2, 2]

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            (b"\x1biK\x0c", b"\x1biK\x04"),  # chain on page 1 only
            (b"\x1biK\x0c", b"\x1biK\x08"),  # half cut dropped
            (b"\x1biA\x01", b"\x1biA\x02"),  # other cut-each
            (b"\x1bid\x0e\x00", b"\x1bid\x0f\x00"),  # other margin
        ],
    )
    def test_second_page_differs(self, old: bytes, new: bytes) -> None:
        """One setting changed on page 1 only is refused at that page."""
        data, printer = self._strip(2, half_cut=True)
        second = data.index(b"\x1bia\x01", 1)
        bad = data[:second] + data[second:].replace(old, new, 1)
        with pytest.raises(InvalidJobError, match=f"byte {second}: page 1: settings differ"):
            validate_job(bad, printer)

    def test_auto_cut_dropped_on_later_page(self) -> None:
        """A page without auto cut (and so without ESC i A) differs too."""
        data, printer = self._strip(2)
        second = data.index(b"\x1bia\x01", 1)
        tail = data[second:].replace(b"\x1biM\x40\x1biA\x01", b"\x1biM\x00", 1)
        with pytest.raises(InvalidJobError, match="settings differ"):
            validate_job(data[:second] + tail, printer)


class TestCutEachPages:
    """With cut-each N the job has a multiple of N pages."""

    def test_remainder_refused(self) -> None:
        """Four pages with cut-each 3 would leave a piece of one."""
        printer = PTE550W(MockConnection())
        pages = [
            printer.build_page(_label(), cut_each=3, feed=i == 3, first_page=i == 0)
            for i in range(4)
        ]
        with pytest.raises(InvalidJobError, match="4 pages is not a multiple of cut-each 3"):
            validate_job(b"".join(pages), printer)

    def test_multiple_accepted(self) -> None:
        """Six pages with cut-each 3 are two pieces."""
        printer = PTE550W(MockConnection())
        job = printer.build_job([_label() for _ in range(6)], cut_each=3)
        assert len(validate_job(job, printer).pages) == 6

    def test_no_auto_cut_no_rule(self) -> None:
        """Strips without auto cut carry no ESC i A and any page count."""
        printer = PTE550W(MockConnection())
        job = printer.build_job([_label() for _ in range(5)], auto_cut=False, half_cut=True)
        assert validate_job(job, printer).pages[0].cut_each is None
