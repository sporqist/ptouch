# ptouch

[![Tests](https://github.com/sporqist/ptouch/actions/workflows/pytest.yml/badge.svg)](https://github.com/sporqist/ptouch/actions/workflows/pytest.yml)
[![Linting](https://github.com/sporqist/ptouch/actions/workflows/lint.yml/badge.svg)](https://github.com/sporqist/ptouch/actions/workflows/lint.yml)

A Python library for Brother P-touch label printers.

> **Fork of [nbuchwitz/ptouch](https://github.com/nbuchwitz/ptouch).**
> Kept compatible with upstream; fixes are offered back as pull requests.
> Additions here: no third-party PackBits dependency (raster lines capped at
> 17 bytes as Brother's reference requires) and a PEP 517 build. Releases
> are on GitHub only, versioned on top of the upstream release they build
> on (e.g. `1.1.0+sporq.1`); the `ptouch` name on PyPI belongs to upstream.
> The documentation linked below is upstream's.

## Features

- Support for Brother P-touch label printers (PT-2730, PT-E550W, PT-P710BT, PT-P750W, PT-P900, PT-P900W, PT-P910BT, PT-P950NW)
- Network (TCP/IP) and USB connections (pyusb, or a device file such as `/dev/usb/lp0`)
- Text labels with customizable fonts and alignment
- Image label printing
- Multi-label printing with half-cut support (saves tape)
- Heat shrink tube support (HSe 2:1 and 3:1 series on PT-E550W/P750W/P900/P900W/P950NW)
- High resolution mode support
- TIFF compression for efficient data transfer

## Installation

```bash
pip install ptouch
```

### Dependencies

- Python 3.11+
- Pillow

For USB support:
- pyusb

## Documentation

Comprehensive documentation is available at [ptouch.readthedocs.io](https://ptouch.readthedocs.io/) including:

- [Quick Start Guide](https://ptouch.readthedocs.io/en/latest/quickstart.html)
- [User Guide](https://ptouch.readthedocs.io/en/latest/userguide.html)
- [Examples](https://ptouch.readthedocs.io/en/latest/examples.html)
- [API Reference](https://ptouch.readthedocs.io/en/latest/api/index.html)
- [Troubleshooting](https://ptouch.readthedocs.io/en/latest/troubleshooting.html)

## Supported Devices

### Printers

| Printer | Resolution | High-Res | Pins | Max Tape Width | Class |
|---------|------------|----------|------|----------------|-------|
| PT-2730 (minimal command set, barely tested) | 180 DPI | - | 128 | 24mm | `PT2730` |
| PT-E550W | 180 DPI | 360 DPI | 128 | 24mm | `PTE550W` |
| PT-P710BT | 180 DPI | 360 DPI | 128 | 24mm | `PTP710BT` |
| PT-P750W | 180 DPI | 360 DPI | 128 | 24mm | `PTP750W` |
| PT-P900 | 360 DPI | 720 DPI | 560 | 36mm | `PTP900` |
| PT-P900W | 360 DPI | 720 DPI | 560 | 36mm | `PTP900W` |
| PT-P910BT | 360 DPI | 720 DPI | 560 | 36mm | `PTP910BT` |
| PT-P950NW | 360 DPI | 720 DPI | 560 | 36mm | `PTP950NW` |

> **PT-2730 hardware notes:** USB only (04F9:2041, status model code
> 63h), TZe tape up to 24 mm, automatic full cutter, no half cut and no
> high resolution. The PT-2730 hangs on the newer raster commands (it stays
> on "receiving data" until switched off), so `PT2730` sets
> `LEGACY_COMMANDS` and gets only the minimal command set that was verified
> on hardware: invalidate, `ESC @`, `ESC i R 01`, `ESC i M 40` (auto cut;
> bit 7 mirror), `ESC i K 08` (cut after the last label; left out for
> chain), uncompressed `G 10 00` + 16 byte raster lines, `0C` between pages,
> `1A` at the end. `ESC i a`, `ESC i z`, `ESC i A`, `ESC i d`, `M`
> (compression) and high resolution are never sent; asking for compression,
> high resolution, a margin, cut-each, special tape or a precut raises
> `ValueError`. The printer adds its own blank tape (**provisional figures**,
> from a handful of prints and one ruler label; verification prints pending): 24.5 mm before the
> first printed line and about 0.5 mm after a single cut label
> (`LEAD_MM`, `TAIL_MM`), roughly 4-5 mm per label in a multi-label job
> (`FEED_PER_LABEL_MM`, approximate). It also feeds about 2.9 % short
> (about 185 instead of 180 lines per inch, measured once, +-0.5 mm):
> `FEED_SCALE` is the stretch factor, applied only on request with
> `printer.stretch_for_feed(image)` or `printer.raster_lines_for_mm(mm)`.
> For a while after a job `ESC i S` reports status type 6 (phase change),
> phase type 1 (printing); that is normal, not a hang. Turn **Editor Lite**
> (mass storage mode) off before printing: in that mode the printer shows
> up as a USB drive and does not take raster data. On Linux the `usblp`
> driver offers the printer as `/dev/usb/lp0`; `ConnectionDevice("/dev/usb/lp0")`
> prints through it without libusb (the user needs access to the node,
> usually the `lp` group).

> **Note:** The PT-P710BT is a basic consumer model and does **not** support half-cut or heat shrink tubes. Its firmware ignores the half-cut command, so use `--full-cut` for multi-label jobs to get a cut between labels.

#### Verified on hardware

Printer models and settings that have been printed on a real device and
checked by eye. Everything else is implemented from Brother's raster
command references but untested on hardware here. The tests in
`TestE550WVerifiedJobs` (`tests/test_printer.py`) pin the verified
command sequences; changing them needs a new hardware check.

| Printer | Firmware | Tape | Verified | What |
|---------|----------|------|----------|------|
| PT-E550W | FP-MAIN 1.31 | TZe-S251 (24mm) | 2026-10-06 | single label; two-label half-cut strip (`print_multi`); PackBits compression; over the network (port 9100); status over SNMP; watchdog states (`hrPrinterStatus` 3 idle, 4 while printing) |
| PT-2730 | - | TZe 24mm laminated | 2026-10-07 | printing with the minimal command set (`LEGACY_COMMANDS`) over `/dev/usb/lp0`: single label, with and without auto cut (`ESC i M 40`); two labels cut each (`ESC i K 08`, `0C` between); two labels uncut (no M/K); `ESC i S` status; 4-dot QR modules at 180 dpi scan; tape use and feed scale measured once, provisional (see `PT2730`) |
| PT-E550W | FP-MAIN 1.31 | TZe-S251 (24mm) | 2026-10-06 | high resolution from 360 dpi images (`high_resolution_image`, K bit 6, 28-dot margin, each line once); half-cut strip in high resolution; cut each N (`cut_each` 2 and 3); free hard cuts as chained jobs with cut each = piece size (pieces 2/1/3, one lead); chained jobs sent back to back on new connections |

Not verified yet on the PT-2730: chain (`ESC i M 40` without `K 08`),
mirror, tapes other than 24 mm. The tests in `TestPT2730Jobs` pin its
verified sequences.

Not verified yet: cut each above 3 (e.g. 55-label pieces), more than three
chained jobs in a run, and splitting one half-cut strip into several
chained jobs.

### Tapes

| Type | Widths | Class | Notes |
|------|--------|-------|-------|
| TZe (Laminated) | 3.5mm, 6mm, 9mm, 12mm, 18mm, 24mm, 36mm | `Tape*mm` | All printers |
| HSe 2:1 (Heat Shrink) | 5.8mm, 8.8mm, 11.7mm, 17.7mm, 23.6mm | `HeatShrinkTube*mm` | E550W/P750W/P900/P900W/P950NW |
| HSe 3:1 (Heat Shrink) | 5.2mm, 9.0mm, 11.2mm, 21.0mm, 31.0mm | `HeatShrinkTube3_1_*mm` | E550W/P750W: up to 21mm; P900: all |

## Adding Support for New Devices

### Adding a New Printer

To add support for a new P-touch printer, create a subclass of `LabelPrinter` in `ptouch/printers.py`:

```python
from ptouch.printer import LabelPrinter, TapeConfig
from ptouch.tape import Tape12mm, Tape24mm  # etc.

class PTP710BT(LabelPrinter):
    """Brother PT-P710BT label printer."""

    # USB product ID (required for USB connections)
    USB_PRODUCT_ID = 0x20XX   # Replace with actual product ID

    # Print head specifications (from Brother raster command reference)
    TOTAL_PINS = 128          # Total pins in print head
    BYTES_PER_LINE = 16       # TOTAL_PINS / 8
    RESOLUTION_DPI = 180      # Base resolution
    RESOLUTION_DPI_HIGH = 360 # High resolution (0 if not supported)

    # Capability flags - what the printer supports
    SUPPORTS_AUTO_CUT = True
    SUPPORTS_HALF_CUT = True
    SUPPORTS_PAGE_NUMBER_CUTS = True

    # Default values for each feature (used when not specified at print time)
    DEFAULT_USE_COMPRESSION = True
    DEFAULT_AUTO_CUT = True
    DEFAULT_HALF_CUT = True
    DEFAULT_HIGH_RESOLUTION = False
    DEFAULT_PAGE_NUMBER_CUTS = False

    # Pin configuration for each tape width
    # Values from Brother raster command reference PDF
    PIN_CONFIGS = {
        Tape12mm: TapeConfig(left_pins=29, print_pins=70, right_pins=29),
        Tape24mm: TapeConfig(left_pins=0, print_pins=128, right_pins=0),
        # Add more tape sizes as needed
    }
```

The pin configuration values (`left_pins`, `print_pins`, `right_pins`) can be found in the
Brother raster command reference documentation for your printer model.

### Adding a New Tape Type

To add a new tape type, create a subclass of `Tape` in `ptouch/tape.py`:

```python
from ptouch.tape import Tape

class Tape48mm(Tape):
    """48mm tape."""
    width_mm = 48
```

Then add the corresponding `TapeConfig` entries to each printer class that supports the tape

## Usage

### Command Line

When the package is installed, the `ptouch` command is available (or use `python -m ptouch` when running from source):

```bash
# Print text label via network (uses PIL default font)
ptouch "Hello World" --host 192.168.1.100 --printer P900 --tape-width 36

# Print with custom font
ptouch "Hello World" --host 192.168.1.100 --printer P900 \
    --tape-width 36 --font /path/to/font.ttf

# Print multiple labels (half-cut between, full cut after last)
ptouch "Label 1" "Label 2" "Label 3" --host 192.168.1.100 \
    --printer P900 --tape-width 12

# Print multiple labels with full cuts between each
ptouch "Label 1" "Label 2" --full-cut --host 192.168.1.100 \
    --printer P900 --tape-width 12

# Print image label via USB
ptouch --image logo.png --usb --printer E550W --tape-width 12

# Print with fixed font size (disables auto-sizing)
ptouch "Test" --host 192.168.1.100 --printer P900 --tape-width 24 \
    --font-size 48 --high-resolution --align left top --margin 5

# Print 5 copies of a label
ptouch "Asset Tag" --copies 5 --host 192.168.1.100 \
    --printer P900 --tape-width 12

# Print label with fixed width (50mm)
ptouch "Short" --width 50 --host 192.168.1.100 \
    --printer P900 --tape-width 12
```

### Python API

#### Text Labels

```python
from ptouch import (
    ConnectionNetwork,
    PTP900,
    TextLabel,
    Tape36mm,
)

# Connect to printer
connection = ConnectionNetwork("192.168.1.100")
printer = PTP900(connection, high_resolution=True)

# Create and print text label
label = TextLabel(
    "Hello World",
    Tape36mm,
    font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    align=TextLabel.Align.CENTER,
)
printer.print(label)

# Or use a pre-loaded ImageFont (auto-sized by default)
from PIL import ImageFont
font = ImageFont.truetype("/path/to/font.ttf", size=48)
label = TextLabel("Custom Font", Tape36mm, font=font)

# Use ImageFont with its built-in size (disable auto-sizing)
label = TextLabel("Fixed Size", Tape36mm, font=font, auto_size=False)

# For quick testing, use the default font (requires Pillow 10.1+)
label = TextLabel("Quick Test", Tape36mm, font=ImageFont.load_default())
```

#### Image Labels

```python
from PIL import Image
from ptouch import ConnectionNetwork, PTP900, Label, Tape36mm

connection = ConnectionNetwork("192.168.1.100")
printer = PTP900(connection)

image = Image.open("label.png")
label = Label(image, Tape36mm)
printer.print(label, margin_mm=3.0)
```

#### USB Connection

```python
from ptouch import ConnectionUSB, PTE550W, TextLabel, Tape12mm

connection = ConnectionUSB()
printer = PTE550W(connection)

label = TextLabel(
    "USB Label",
    Tape12mm,
    font="/path/to/font.ttf",
)
printer.print(label)
```

#### Device File (Linux usblp)

```python
from ptouch import ConnectionDevice, PT2730, TextLabel, Tape24mm

connection = ConnectionDevice("/dev/usb/lp0")  # or "file:///dev/usb/lp0"
printer = PT2730(connection)
print(connection.read_status().tape)  # ESC i S, 32-byte reply
printer.print(TextLabel("Device file", Tape24mm, font="/path/to/font.ttf"))
```

`read_status()` (send `ESC i S`, read the 32-byte block with a timeout)
works on USB connections too, `ConnectionUSB` and `ConnectionDevice`.

#### Multi-Label Printing

Print multiple labels in a single job with half-cuts between labels to save tape:

```python
from ptouch import ConnectionNetwork, PTP900, TextLabel, Tape12mm

connection = ConnectionNetwork("192.168.1.100")
printer = PTP900(connection)

labels = [
    TextLabel("Label 1", Tape12mm, font="/path/to/font.ttf"),
    TextLabel("Label 2", Tape12mm, font="/path/to/font.ttf"),
    TextLabel("Label 3", Tape12mm, font="/path/to/font.ttf"),
]

# Half-cuts between labels (default), full cut after last
printer.print_multi(labels)

# Or use full cuts between all labels
printer.print_multi(labels, half_cut=False)
```

### Printer Status (network printers)

Network P-touch printers do not answer status requests on the print port,
but they publish the same 32-byte status block over SNMP. Read it before
printing to check the loaded tape and error flags:

```python
from ptouch.snmp import read_status

status = read_status("192.168.1.101")
print(status.tape)          # "24 mm laminated tape, black on white"
print(status.has_error, status.errors, status.is_printing)
```

Verified on a PT-E550W. Needs SNMP v1 with the default community `public`.

### Alignment Options

Text alignment can be combined using the `|` operator:

```python
from ptouch import TextLabel

# Horizontal: LEFT, HCENTER, RIGHT
# Vertical: TOP, VCENTER, BOTTOM
# Combined: CENTER (= HCENTER | VCENTER)

align = TextLabel.Align.LEFT | TextLabel.Align.TOP
align = TextLabel.Align.RIGHT | TextLabel.Align.BOTTOM
align = TextLabel.Align.CENTER  # centered both ways
```

Note: `Align` is also available as a backwards-compatible alias at package level.

## CLI Options

```
usage: ptouch [-h] [--image FILE] (--host IP | --usb | --device PATH)
              --printer {2730,E550W,P710BT,P750W,P900,P900W,P910BT,P950NW}
              --tape-width {3.5,6,9,12,18,24,36} [--font PATH] [--font-size PX]
              [--align H V] [--high-resolution] [--margin MM] [--no-compression]
              [--full-cut] [--precut] [--copies N] [--width MM] [text ...]

positional arguments:
  text                  Text to print. Multiple strings create multiple labels
                        with half-cut between (required unless --image is used)

options:
  --image, -i FILE      Image file to print instead of text
  --host, -H IP         Printer IP address for network connection
  --usb                 Use USB connection
  --device PATH         Printer device file, e.g. /dev/usb/lp0
  --printer, -p         Printer model
  --tape-width, -t      Tape width in mm
  --font, -f PATH       Path to TrueType font file (uses PIL default if not specified)
  --font-size PX        Font size in pixels (disables auto-sizing to 80% of print height)
  --align, -a H V       Horizontal and vertical alignment (default: center center)
  --high-resolution     Enable high resolution mode
  --margin, -m MM       Margin in mm (default: 2mm)
  --no-compression      Disable TIFF compression
  --full-cut            Use full cuts between labels instead of half-cuts
  --precut              Eject the ~24mm leader between the print head and
                        cutter as a scrap before the first label, so the
                        label starts at a fresh cut edge with no blank tape
  --copies, -c N        Number of copies to print (default: 1)
  --width, -w MM        Fixed label width in mm (default: auto-sized to content)
```

## Error Handling

The library provides a hierarchy of exception classes for targeted error handling:

```python
from ptouch import (
    PrinterConnectionError,     # Base exception for all connection errors
    PrinterNotFoundError,        # Printer device not found
    PrinterPermissionError,      # Permission denied (USB requires sudo/udev rules)
    PrinterNetworkError,         # Network connection/communication errors
    PrinterTimeoutError,         # Connection or operation timeout
    PrinterWriteError,           # Failed to write data to printer
)

try:
    printer.print(label)
except PrinterPermissionError:
    print("Permission denied. Try running with sudo or configure udev rules.")
except PrinterTimeoutError:
    print("Printer not responding. Check connection and power.")
except PrinterNotFoundError:
    print("Printer not found. Check if device is connected.")
except PrinterConnectionError:
    print("General connection error occurred.")
```

All specific exceptions inherit from `PrinterConnectionError`, allowing you to catch all connection-related errors with a single except clause, or handle specific error types individually for more targeted error handling.

## License

LGPL-2.1-or-later - see [LICENSE](LICENSE) for details.

## Author

Nicolai Buchwitz <nb@tipi-net.de>
