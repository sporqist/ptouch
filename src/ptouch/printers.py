# SPDX-FileCopyrightText: 2024-2026 Nicolai Buchwitz <nb@tipi-net.de>
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Concrete printer implementations for Brother P-touch label printers."""

from .printer import LabelPrinter, MediaType, TapeConfig
from .tape import (
    HeatShrinkTube3_1_5_2mm,
    HeatShrinkTube3_1_9_0mm,
    HeatShrinkTube3_1_11_2mm,
    HeatShrinkTube3_1_21_0mm,
    HeatShrinkTube3_1_31_0mm,
    HeatShrinkTube5_8mm,
    HeatShrinkTube8_8mm,
    HeatShrinkTube11_7mm,
    HeatShrinkTube17_7mm,
    HeatShrinkTube23_6mm,
    Tape3_5mm,
    Tape6mm,
    Tape9mm,
    Tape12mm,
    Tape18mm,
    Tape24mm,
    Tape36mm,
)


class PTE550W(LabelPrinter):
    """Brother PT-E550W label printer (128 pins, 180 DPI).

    Note: E550W requires compression ON for cutting to work.
    High resolution mode (180x360 dpi) is supported via ESC i K bit 6.
    In high-res mode the margin is doubled, and a normal-resolution image
    has each raster line sent twice; an image already at 360 dpi along the
    tape is sent line by line (``build_page(high_resolution_image=True)``).
    """

    USB_PRODUCT_ID = 0x2060
    # TZe tape is laminated (01h); 00h would mean "no tape" on this family.
    TAPE_MEDIA_TYPE = MediaType.LAMINATED_TAPE
    # The raster reference specifies a 100-byte invalidate for this family.
    INVALIDATE_BYTES = 100
    TOTAL_PINS = 128
    BYTES_PER_LINE = 16
    RESOLUTION_DPI = 180
    RESOLUTION_DPI_HIGH = 360
    DEFAULT_USE_COMPRESSION = True  # Required for cutting to work

    # Pin configurations from official Brother PT-E550W specification document
    # Source: cv_pte550wp750wp710bt_eng_raster_102.pdf, page 20, section "2.3 Print Area"
    PIN_CONFIGS = {
        # Laminated tapes (TZe series)
        Tape3_5mm: TapeConfig(left_pins=52, print_pins=24, right_pins=52),
        Tape6mm: TapeConfig(left_pins=48, print_pins=32, right_pins=48),
        Tape9mm: TapeConfig(left_pins=39, print_pins=50, right_pins=39),
        Tape12mm: TapeConfig(left_pins=29, print_pins=70, right_pins=29),
        Tape18mm: TapeConfig(left_pins=8, print_pins=112, right_pins=8),
        Tape24mm: TapeConfig(left_pins=0, print_pins=128, right_pins=0),
        # Heat shrink tubes 2:1 series (HSe)
        # Corrected configs: shifted -2 pins (up) based on testing
        HeatShrinkTube5_8mm: TapeConfig(left_pins=52, print_pins=28, right_pins=48),
        HeatShrinkTube8_8mm: TapeConfig(left_pins=42, print_pins=48, right_pins=38),
        HeatShrinkTube11_7mm: TapeConfig(left_pins=33, print_pins=66, right_pins=29),
        HeatShrinkTube17_7mm: TapeConfig(left_pins=13, print_pins=106, right_pins=9),
        HeatShrinkTube23_6mm: TapeConfig(left_pins=0, print_pins=128, right_pins=0),
        # Heat shrink tubes 3:1 series (HSe)
        HeatShrinkTube3_1_5_2mm: TapeConfig(left_pins=56, print_pins=20, right_pins=52),
        HeatShrinkTube3_1_9_0mm: TapeConfig(left_pins=44, print_pins=44, right_pins=40),
        HeatShrinkTube3_1_11_2mm: TapeConfig(left_pins=41, print_pins=50, right_pins=37),
        HeatShrinkTube3_1_21_0mm: TapeConfig(left_pins=6, print_pins=120, right_pins=2),
        # Note: PT-E550W/P750W do NOT support 31.0mm 3:1 tubes
    }


class PTP750W(PTE550W):
    """Brother PT-P750W label printer (128 pins, 180 DPI).

    Inherits all settings from PTE550W.
    """

    USB_PRODUCT_ID = 0x2065


class PTP710BT(PTE550W):
    """Brother PT-P710BT label printer (128 pins, 180 DPI, Bluetooth/USB).

    Same raster protocol as PT-E550W / PT-P750W (covered by the same
    Brother spec document: cv_pte550wp750wp710bt_eng_raster_102.pdf).

    Note: PT-P710BT supports only laminated TZe tapes — no heat shrink
    tubes (HSe series) and no 36 mm tape (the 128-pin head caps at 24 mm).
    """

    USB_PRODUCT_ID = 0x20AF

    # PT-P710BT does not support half-cut (basic consumer model — half-cut
    # is a feature of the higher-end PT-E / PT-P series). The firmware
    # silently ignores the half-cut bit, so default to full cuts.
    SUPPORTS_HALF_CUT = False
    DEFAULT_HALF_CUT = False

    # PT-P710BT only supports laminated TZe tapes (3.5 / 6 / 9 / 12 / 18 / 24 mm).
    PIN_CONFIGS = {
        Tape3_5mm: TapeConfig(left_pins=52, print_pins=24, right_pins=52),
        Tape6mm: TapeConfig(left_pins=48, print_pins=32, right_pins=48),
        Tape9mm: TapeConfig(left_pins=39, print_pins=50, right_pins=39),
        Tape12mm: TapeConfig(left_pins=29, print_pins=70, right_pins=29),
        Tape18mm: TapeConfig(left_pins=8, print_pins=112, right_pins=8),
        Tape24mm: TapeConfig(left_pins=0, print_pins=128, right_pins=0),
    }


class PT2730(LabelPrinter):
    """Brother PT-2730 label printer (128 pins, 180 DPI, USB only).

    Printing verified on hardware (2026-10-07, USB through ``/dev/usb/lp0``,
    24 mm TZe laminated tape, status model code 63h) with the legacy
    command set (``LEGACY_COMMANDS``, see :class:`~ptouch.printer.LabelPrinter`):

    - The PT-E550W-style job (ESC i a, ESC i z, ESC i M, ESC i A, ESC i K,
      ESC i d, M 00, uncompressed lines, 1A) hangs the printer: it stays
      on "receiving data" until it is switched off. Which of those
      commands it chokes on is not known.
    - ESC i R 01, uncompressed lines, 1A prints. Without ESC i M the
      printer's own menu setting decides about the cut.
    - ESC i R 01, ESC i M 40, lines, 1A prints and cuts cleanly.
    - ESC i R 01, ESC i M 40, ESC i K 08, page 1, 0C, page 2, 1A gives two
      separately cut labels.
    - The same two pages without ESC i M and ESC i K come out as one uncut
      piece (about 61 mm blank in front).

    The margin cannot be set (no ESC i d); the printer adds its own blank
    tape. Measured 2026-10-07 on 24 mm TZe:

    - Feed pitch: on a 60 mm ruler label (425 lines, a full-height line at
      dot 423 = 59.7 mm nominal) the first to the last line measured
      58 mm, so the tape moves about 2.9 % short (about 185 lines per inch
      instead of 180). ``FEED_SCALE`` = 59.7/58 is the factor to stretch
      an image along the tape by so physical lengths come out true;
      nothing applies it unless asked (:meth:`~ptouch.printer.LabelPrinter.
      stretch_for_feed`, :meth:`~ptouch.printer.LabelPrinter.raster_lines_for_mm`).
    - Single cut label (ESC i R 01, ESC i M 40, lines, 1A): 24.5 mm blank
      before the first printed line (``LEAD_MM``, print head to cutter),
      83 mm whole piece, so about 0.5 mm after the content (``TAIL_MM``).
    - Two labels cut each (0C between): each label about 23 mm for about
      17.7 mm of content, so roughly 4-5 mm added per label
      (``FEED_PER_LABEL_MM``, approximate; measured before the feed-scale
      correction). Without any cut the two labels had about 61 mm blank
      in front.

    Status: ``Connection.read_status()`` (ESC i S) answers over the same
    device connection. For a while after a job the printer reports status
    type 6 (phase change) with phase type 1 (printing); that is normal and
    not a hang.

    Brother publishes no raster command reference for this model. The other
    values come from Brother's PT-2730 User's Guide (Specifications, Tape
    Cutting Options), the ``ptouch-print`` device table
    (git.familie-radermacher.ch/linux/ptouch-print.git, ``src/libptouch.c``)
    and the linux-usb.org ``usb.ids`` list. Where those say nothing, the
    PT-E550W/P750W/P710BT raster reference (same 128-pin, 180 dpi head) is
    used and the comment says "assumed".

    The printer must not be in Editor Lite (mass storage) mode; raster data
    only reaches it on its printer-class USB interface.
    """

    # 04F9:2041: ptouch-print's device table ("PT-2730") and usb.ids
    # ("PT-2730 P-touch Label Printer") agree; lsusb on the target host too.
    USB_PRODUCT_ID = 0x2041
    # Only the minimal command set; see LabelPrinter.LEGACY_COMMANDS.
    LEGACY_COMMANDS = True
    # Media type for ESC i z, which this model is never sent. Kept for
    # completeness: the status block reports TZe as laminated (01h).
    TAPE_MEDIA_TYPE = MediaType.LAMINATED_TAPE
    # 100-byte invalidate, as in the jobs verified on hardware.
    INVALIDATE_BYTES = 100
    # "Print head: 128 dot / 180 dpi" (User's Guide, Specifications).
    TOTAL_PINS = 128
    BYTES_PER_LINE = 16
    RESOLUTION_DPI = 180
    # No high resolution: the specifications list 180 dpi only.
    RESOLUTION_DPI_HIGH = 0
    # Uncompressed only: the M command is not sent (see LEGACY_COMMANDS).
    DEFAULT_USE_COMPRESSION = False

    # User's Guide cutting options: Large Margin, Small Margin, Chain,
    # No Cut, Special Tape. An automatic full cutter, no half cut.
    SUPPORTS_HALF_CUT = False
    DEFAULT_HALF_CUT = False
    # No ESC i A (cut each N) and no ESC i K special-tape bit.
    SUPPORTS_PAGE_NUMBER_CUTS = False
    SUPPORTS_SPECIAL_TAPE = False

    # Tape use for length estimates, measured 2026-10-07 on 24 mm TZe (no
    # ESC i d to change any of it). See the class docstring.
    # Feed correction, measured once 2026-10-07 (+-0.5 mm): 423 dots
    # (59.7 mm nominal) printed 58 mm long. Stretch factor along the tape.
    FEED_SCALE: float = 59.7 / 58
    # Single cut label: blank before the first printed line and after the
    # content (83 mm piece for 58 mm of content).
    LEAD_MM: float = 24.5
    TAIL_MM: float = 0.5
    # Approximate, from a two-label cut-each job measured before the
    # feed-scale correction: ~23 mm per label for ~17.7 mm of content.
    FEED_PER_LABEL_MM: float = 5.0

    # TZe tape 3.5-24 mm (User's Guide, Specifications). Print areas assumed
    # from the same head in cv_pte550wp750wp710bt_eng_raster_102.pdf,
    # section 2.3 "Print Area". ptouch-print's table has slightly wider
    # areas (9 mm 52, 12 mm 76, 18 mm 120 pins); Brother's figures win.
    PIN_CONFIGS = {
        Tape3_5mm: TapeConfig(left_pins=52, print_pins=24, right_pins=52),
        Tape6mm: TapeConfig(left_pins=48, print_pins=32, right_pins=48),
        Tape9mm: TapeConfig(left_pins=39, print_pins=50, right_pins=39),
        Tape12mm: TapeConfig(left_pins=29, print_pins=70, right_pins=29),
        Tape18mm: TapeConfig(left_pins=8, print_pins=112, right_pins=8),
        Tape24mm: TapeConfig(left_pins=0, print_pins=128, right_pins=0),
    }


class PTP900Series(LabelPrinter):
    """Base class for Brother PT-P900 series printers (560 pins, 360 DPI).

    This is the base class for all P900 series printers. Use one of the
    specific subclasses (PTP900, PTP900W, PTP950NW, PTP910BT) instead.
    """

    TOTAL_PINS = 560
    BYTES_PER_LINE = 70
    RESOLUTION_DPI = 360
    RESOLUTION_DPI_HIGH = 720
    DEFAULT_USE_COMPRESSION = False

    # Pin configurations from official Brother PT-P900 specification document
    # Source: cv_ptp900_eng_raster_102.pdf, pages 23-24, section 2.3.5 "Raster line"
    PIN_CONFIGS = {
        # Laminated tapes (TZe series)
        Tape3_5mm: TapeConfig(left_pins=248, print_pins=48, right_pins=264),
        Tape6mm: TapeConfig(left_pins=240, print_pins=64, right_pins=256),
        Tape9mm: TapeConfig(left_pins=219, print_pins=106, right_pins=235),
        Tape12mm: TapeConfig(left_pins=197, print_pins=150, right_pins=213),
        Tape18mm: TapeConfig(left_pins=155, print_pins=234, right_pins=171),
        Tape24mm: TapeConfig(left_pins=112, print_pins=320, right_pins=128),
        Tape36mm: TapeConfig(left_pins=45, print_pins=454, right_pins=61),
        # Heat shrink tubes 2:1 series (HSe)
        # Corrected configs: shifted +17 pins down based on Brother software analysis
        HeatShrinkTube5_8mm: TapeConfig(left_pins=261, print_pins=56, right_pins=243),
        HeatShrinkTube8_8mm: TapeConfig(left_pins=241, print_pins=96, right_pins=223),
        HeatShrinkTube11_7mm: TapeConfig(left_pins=223, print_pins=132, right_pins=205),
        HeatShrinkTube17_7mm: TapeConfig(left_pins=183, print_pins=212, right_pins=165),
        HeatShrinkTube23_6mm: TapeConfig(left_pins=161, print_pins=256, right_pins=143),
        # Heat shrink tubes 3:1 series (HSe)
        HeatShrinkTube3_1_5_2mm: TapeConfig(left_pins=269, print_pins=40, right_pins=251),
        HeatShrinkTube3_1_9_0mm: TapeConfig(left_pins=245, print_pins=88, right_pins=227),
        HeatShrinkTube3_1_11_2mm: TapeConfig(left_pins=239, print_pins=100, right_pins=221),
        HeatShrinkTube3_1_21_0mm: TapeConfig(left_pins=169, print_pins=240, right_pins=151),
        HeatShrinkTube3_1_31_0mm: TapeConfig(left_pins=109, print_pins=360, right_pins=91),
    }


class PTP900(PTP900Series):
    """Brother PT-P900 label printer (USB only, no wireless)."""

    USB_PRODUCT_ID = 0x2083


class PTP900W(PTP900Series):
    """Brother PT-P900W label printer (with Wi-Fi)."""

    USB_PRODUCT_ID = 0x2085


class PTP950NW(PTP900Series):
    """Brother PT-P950NW label printer (with network connectivity)."""

    USB_PRODUCT_ID = 0x2086


class PTP910BT(PTP900Series):
    """Brother PT-P910BT label printer (with Bluetooth).

    Note: PT-P910BT does NOT support heat shrink tubes (HSe series).
    """

    USB_PRODUCT_ID = 0x20C7

    # PT-P910BT only supports laminated tapes, not heat shrink tubes
    PIN_CONFIGS = {
        Tape3_5mm: TapeConfig(left_pins=248, print_pins=48, right_pins=264),
        Tape6mm: TapeConfig(left_pins=240, print_pins=64, right_pins=256),
        Tape9mm: TapeConfig(left_pins=219, print_pins=106, right_pins=235),
        Tape12mm: TapeConfig(left_pins=197, print_pins=150, right_pins=213),
        Tape18mm: TapeConfig(left_pins=155, print_pins=234, right_pins=171),
        Tape24mm: TapeConfig(left_pins=112, print_pins=320, right_pins=128),
        Tape36mm: TapeConfig(left_pins=45, print_pins=454, right_pins=61),
    }
