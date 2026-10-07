# SPDX-FileCopyrightText: 2024-2026 Nicolai Buchwitz <nb@tipi-net.de>
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for the ptouch.printer and ptouch.printers modules."""

import pytest
from PIL import Image

from ptouch.label import Label
from ptouch.printer import TapeConfig
from ptouch.printer import MediaType
from ptouch.printers import PT2730, PTE550W, PTP750W, PTP900
from ptouch.tape import (
    Tape3_5mm,
    Tape6mm,
    Tape12mm,
    Tape24mm,
    Tape36mm,
)

from .conftest import MockConnection, job_commands


class TestMediaType:
    """Test MediaType enum."""

    def test_media_type_values(self) -> None:
        """Test that MediaType enum has expected values."""
        assert MediaType.NO_MEDIA.value == 0x00
        assert MediaType.LAMINATED_TAPE.value == 0x01
        assert MediaType.NONLAMINATED_TAPE.value == 0x03
        assert MediaType.HEATSHRINK_TUBE_21.value == 0x11
        assert MediaType.INCOMPATIBLE_TAPE.value == 0xFF


class TestPTE550W:
    """Test PTE550W printer class."""

    def test_class_attributes(self) -> None:
        """Test that class attributes are correctly defined."""
        assert PTE550W.TOTAL_PINS == 128
        assert PTE550W.BYTES_PER_LINE == 16
        assert PTE550W.RESOLUTION_DPI == 180
        assert PTE550W.RESOLUTION_DPI_HIGH == 360
        assert PTE550W.DEFAULT_USE_COMPRESSION is True

    def test_initialization(self, mock_connection: MockConnection) -> None:
        """Test printer initialization."""
        printer = PTE550W(mock_connection)
        assert printer.connection is mock_connection
        assert printer.use_compression is True  # Default
        assert printer.high_resolution is False  # Default

    def test_initialization_with_custom_settings(self, mock_connection: MockConnection) -> None:
        """Test printer initialization with custom settings."""
        printer = PTE550W(mock_connection, use_compression=False, high_resolution=True)
        assert printer.use_compression is False
        assert printer.high_resolution is True

    def test_supports_high_resolution(self, mock_connection: MockConnection) -> None:
        """Test that E550W supports high resolution."""
        printer = PTE550W(mock_connection)
        assert printer.supports_high_resolution is True

    def test_pin_configs(self) -> None:
        """Test that PIN_CONFIGS contains expected tape types."""
        assert Tape3_5mm in PTE550W.PIN_CONFIGS
        assert Tape6mm in PTE550W.PIN_CONFIGS
        assert Tape12mm in PTE550W.PIN_CONFIGS
        assert Tape24mm in PTE550W.PIN_CONFIGS
        # E550W doesn't support 36mm
        assert Tape36mm not in PTE550W.PIN_CONFIGS

    def test_get_tape_config(self, mock_connection: MockConnection) -> None:
        """Test getting tape configuration."""
        printer = PTE550W(mock_connection)
        tape = Tape12mm()
        config = printer.get_tape_config(tape)
        assert isinstance(config, TapeConfig)
        assert config.left_pins == 29
        assert config.print_pins == 70
        assert config.right_pins == 29
        # Total should equal TOTAL_PINS
        assert config.left_pins + config.print_pins + config.right_pins == 128

    def test_get_tape_config_unsupported_tape(self, mock_connection: MockConnection) -> None:
        """Test that unsupported tape raises ValueError."""
        printer = PTE550W(mock_connection)
        tape = Tape36mm()
        with pytest.raises(ValueError, match="not supported"):
            printer.get_tape_config(tape)


class TestSupportedTapes:
    """Test supported_tapes property."""

    def test_supported_tapes_returns_list(self, mock_connection: MockConnection) -> None:
        """Test that supported_tapes returns a list of tape classes."""
        printer = PTE550W(mock_connection)
        tapes = printer.supported_tapes
        assert isinstance(tapes, list)
        assert len(tapes) > 0
        assert Tape6mm in tapes
        assert Tape12mm in tapes
        assert Tape24mm in tapes

    def test_supported_tapes_sorted_by_name(self, mock_connection: MockConnection) -> None:
        """Test that supported_tapes are sorted by class name."""
        printer = PTE550W(mock_connection)
        tapes = printer.supported_tapes
        names = [t.__name__ for t in tapes]
        assert names == sorted(names)

    def test_supported_tapes_excludes_unsupported(self, mock_connection: MockConnection) -> None:
        """Test that E550W doesn't include 36mm tape."""
        printer = PTE550W(mock_connection)
        tapes = printer.supported_tapes
        assert Tape36mm not in tapes

    def test_p900_supports_36mm(self, mock_connection: MockConnection) -> None:
        """Test that P900 includes 36mm tape."""
        printer = PTP900(mock_connection)
        assert Tape36mm in printer.supported_tapes


class TestPTP750W:
    """Test PTP750W printer class."""

    def test_inherits_from_e550w(self) -> None:
        """Test that P750W inherits from E550W."""
        assert issubclass(PTP750W, PTE550W)

    def test_same_attributes_as_e550w(self) -> None:
        """Test that P750W has same attributes as E550W."""
        assert PTP750W.TOTAL_PINS == PTE550W.TOTAL_PINS
        assert PTP750W.PIN_CONFIGS == PTE550W.PIN_CONFIGS


class TestPTP900:
    """Test PTP900 printer class."""

    def test_class_attributes(self) -> None:
        """Test that class attributes are correctly defined."""
        assert PTP900.TOTAL_PINS == 560
        assert PTP900.BYTES_PER_LINE == 70
        assert PTP900.RESOLUTION_DPI == 360
        assert PTP900.RESOLUTION_DPI_HIGH == 720
        assert PTP900.DEFAULT_USE_COMPRESSION is False

    def test_supports_36mm_tape(self) -> None:
        """Test that P900 supports 36mm tape."""
        assert Tape3_5mm in PTP900.PIN_CONFIGS
        assert Tape36mm in PTP900.PIN_CONFIGS

    def test_get_tape_config_36mm(self, mock_connection: MockConnection) -> None:
        """Test getting 36mm tape configuration."""
        printer = PTP900(mock_connection)
        tape = Tape36mm()
        config = printer.get_tape_config(tape)
        assert config.left_pins == 45
        assert config.print_pins == 454
        assert config.right_pins == 61
        assert config.left_pins + config.print_pins + config.right_pins == 560


class TestLabelPrinterCommands:
    """Test LabelPrinter command generation methods."""

    @pytest.fixture
    def printer(self, mock_connection: MockConnection) -> PTE550W:
        """Create a test printer."""
        return PTE550W(mock_connection)

    def test_cmd_invalidate(self, printer: PTE550W) -> None:
        """Test invalidate command generates correct null bytes."""
        cmd = printer._cmd_invalidate(length=100)
        assert len(cmd) == 100
        assert cmd == b"\x00" * 100

    def test_cmd_initialize(self, printer: PTE550W) -> None:
        """Test initialize command (ESC @)."""
        cmd = printer._cmd_initialize()
        assert cmd == b"\x1b\x40"

    def test_cmd_raster_mode(self, printer: PTE550W) -> None:
        """Test raster mode command (ESC i a)."""
        cmd = printer._cmd_raster_mode()
        assert cmd == b"\x1b\x69\x61\x01"

    def test_cmd_mode_settings_auto_cut_on(self, printer: PTE550W) -> None:
        """Test mode settings with auto-cut enabled."""
        cmd = printer._cmd_mode_settings(auto_cut=True, mirror_print=False)
        assert cmd[:3] == b"\x1b\x69\x4d"
        assert cmd[3] & (1 << 6) != 0  # Auto-cut bit set

    def test_cmd_mode_settings_auto_cut_off(self, printer: PTE550W) -> None:
        """Test mode settings with auto-cut disabled."""
        cmd = printer._cmd_mode_settings(auto_cut=False, mirror_print=False)
        assert cmd[:3] == b"\x1b\x69\x4d"
        assert cmd[3] & (1 << 6) == 0  # Auto-cut bit not set

    def test_cmd_advanced_mode_settings_high_res(self, printer: PTE550W) -> None:
        """Test advanced mode settings with high resolution enabled."""
        cmd = printer._cmd_advanced_mode_settings(high_resolution=True)
        assert cmd[:3] == b"\x1b\x69\x4b"
        assert cmd[3] & (1 << 6) != 0  # High-res bit set

    def test_cmd_margin(self, printer: PTE550W) -> None:
        """Test margin command."""
        cmd = printer._cmd_margin(margin=14)
        assert cmd[:3] == b"\x1b\x69\x64"
        # Margin is little-endian 16-bit
        assert cmd[3:5] == b"\x0e\x00"

    def test_cmd_set_compression_on(self, printer: PTE550W) -> None:
        """Test compression command enabled."""
        cmd = printer._cmd_set_compression(tiff_compression=True)
        assert cmd == b"\x4d\x02"

    def test_cmd_set_compression_off(self, printer: PTE550W) -> None:
        """Test compression command disabled."""
        cmd = printer._cmd_set_compression(tiff_compression=False)
        assert cmd == b"\x4d\x00"


class TestLabelPrinterMmToDots:
    """Test mm to dots conversion."""

    def test_mm_to_dots_e550w(self, mock_connection: MockConnection) -> None:
        """Test mm to dots conversion for 180 DPI printer."""
        printer = PTE550W(mock_connection)  # 180 DPI
        # 25.4mm = 1 inch = 180 dots
        assert printer._mm_to_dots(25.4) == 180
        # 2mm margin
        dots = printer._mm_to_dots(2.0)
        assert dots == round(2.0 * 180 / 25.4)  # ~14

    def test_mm_to_dots_p900(self, mock_connection: MockConnection) -> None:
        """Test mm to dots conversion for 360 DPI printer."""
        printer = PTP900(mock_connection)  # 360 DPI
        # 25.4mm = 1 inch = 360 dots
        assert printer._mm_to_dots(25.4) == 360


class TestLabelPrinterPrint:
    """Test the complete print workflow."""

    def test_print_sends_data(
        self, mock_connection: MockConnection, sample_image_with_content: Image.Image
    ) -> None:
        """Test that print sends data to the connection."""
        printer = PTE550W(mock_connection, use_compression=True)
        label = Label(sample_image_with_content, Tape12mm)
        printer.print(label)
        # Should have sent data
        assert len(mock_connection.data) > 0
        # Should start with invalidate (null bytes)
        assert mock_connection.data[:50] == b"\x00" * 50

    def test_print_with_custom_margin(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test print with custom margin."""
        printer = PTE550W(mock_connection)
        label = Label(sample_image, Tape12mm)
        printer.print(label, margin_mm=5.0)
        assert len(mock_connection.data) > 0

    def test_print_invalid_margin_too_small(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test that margin below minimum raises ValueError."""
        printer = PTE550W(mock_connection)
        label = Label(sample_image, Tape12mm)
        with pytest.raises(ValueError, match="Margin must be between"):
            printer.print(label, margin_mm=0.5)

    def test_print_invalid_margin_too_large(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test that margin above maximum raises ValueError."""
        printer = PTE550W(mock_connection)
        label = Label(sample_image, Tape12mm)
        with pytest.raises(ValueError, match="Margin must be between"):
            printer.print(label, margin_mm=200.0)

    def test_print_unsupported_tape(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test that printing with unsupported tape raises ValueError."""
        printer = PTE550W(mock_connection)
        label = Label(sample_image, Tape36mm)  # E550W doesn't support 36mm
        with pytest.raises(ValueError, match="not supported"):
            printer.print(label)

    def test_print_with_high_resolution(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test printing in high resolution mode."""
        printer = PTE550W(mock_connection)
        label = Label(sample_image, Tape12mm)
        printer.print(label, high_resolution=True)
        assert len(mock_connection.data) > 0

    def test_print_ends_with_print_command(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test that print data ends with print command (0x1a) and initialize."""
        printer = PTE550W(mock_connection, use_compression=True)
        label = Label(sample_image, Tape12mm)
        printer.print(label)
        # Should contain print command
        assert b"\x1a" in mock_connection.data


class TestImagePreparation:
    """Test image preparation methods."""

    def test_prepare_image_returns_1bit(self, mock_connection: MockConnection) -> None:
        """Test that _prepare_image returns a 1-bit image."""
        printer = PTE550W(mock_connection)
        img = Image.new("RGB", (100, 50), color=(255, 255, 255))
        tape = Tape12mm()
        config = printer.get_tape_config(tape)
        img_1bit = printer._prepare_image(img, config)
        assert img_1bit.mode == "1"

    def test_prepare_image_matches_print_pins_height(self, mock_connection: MockConnection) -> None:
        """Test that prepared image height matches print_pins."""
        printer = PTE550W(mock_connection)
        img = Image.new("RGB", (100, 50), color=(255, 255, 255))
        tape = Tape12mm()
        config = printer.get_tape_config(tape)
        img_1bit = printer._prepare_image(img, config)
        assert img_1bit.height == config.print_pins

    def test_generate_raster_correct_length(self, mock_connection: MockConnection) -> None:
        """Test that raster data has correct length."""
        printer = PTE550W(mock_connection)
        img = Image.new("RGB", (100, 50), color=(255, 255, 255))
        tape = Tape12mm()
        config = printer.get_tape_config(tape)
        img_1bit = printer._prepare_image(img, config)
        raster = printer._generate_raster(img_1bit, config)
        # Each column should have BYTES_PER_LINE bytes
        expected_length = img_1bit.width * printer.BYTES_PER_LINE
        assert len(raster) == expected_length


class TestLabelPrinterPrintMulti:
    """Test the print_multi workflow for multiple labels."""

    def test_print_multi_sends_data(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test that print_multi sends data to the connection."""
        printer = PTE550W(mock_connection, use_compression=True)
        labels = [
            Label(sample_image, Tape12mm),
            Label(sample_image, Tape12mm),
        ]
        printer.print_multi(labels)
        # Should have sent data
        assert len(mock_connection.data) > 0
        # Should start with invalidate (null bytes)
        assert mock_connection.data[:50] == b"\x00" * 50

    def test_print_multi_single_label(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test that print_multi with a single label works correctly."""
        printer = PTE550W(mock_connection, use_compression=True)
        labels = [Label(sample_image, Tape12mm)]
        printer.print_multi(labels)
        # Should have sent data
        assert len(mock_connection.data) > 0
        # Single label should end with print command (0x1a)
        assert b"\x1a" in mock_connection.data

    def test_print_multi_empty_list_raises_error(self, mock_connection: MockConnection) -> None:
        """Test that print_multi with empty list raises ValueError."""
        printer = PTE550W(mock_connection)
        with pytest.raises(ValueError, match="(?i)at least one label"):
            printer.print_multi([])

    def test_print_multi_mismatched_tapes_raises_error(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test that print_multi with different tape types raises ValueError."""
        printer = PTE550W(mock_connection)
        labels = [
            Label(sample_image, Tape12mm),
            Label(sample_image, Tape6mm),
        ]
        with pytest.raises(ValueError, match="same tape type"):
            printer.print_multi(labels)

    def test_print_multi_contains_form_feed_between_labels(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test that multi-label print has form feed (0x0C) between labels."""
        printer = PTE550W(mock_connection, use_compression=True)
        labels = [
            Label(sample_image, Tape12mm),
            Label(sample_image, Tape12mm),
        ]
        printer.print_multi(labels)
        # Form feed (0x0C) should appear between labels (not at end)
        assert b"\x0c" in mock_connection.data

    def test_print_multi_ends_with_print_command(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test that multi-label print ends with print command (0x1a)."""
        printer = PTE550W(mock_connection, use_compression=True)
        labels = [
            Label(sample_image, Tape12mm),
            Label(sample_image, Tape12mm),
        ]
        printer.print_multi(labels)
        # Should contain final print command
        assert b"\x1a" in mock_connection.data

    def test_print_multi_unsupported_tape(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test that printing with unsupported tape raises ValueError."""
        printer = PTE550W(mock_connection)
        labels = [
            Label(sample_image, Tape36mm),  # E550W doesn't support 36mm
            Label(sample_image, Tape36mm),
        ]
        with pytest.raises(ValueError, match="not supported"):
            printer.print_multi(labels)

    def test_print_multi_with_custom_margin(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test print_multi with custom margin."""
        printer = PTE550W(mock_connection)
        labels = [
            Label(sample_image, Tape12mm),
            Label(sample_image, Tape12mm),
        ]
        printer.print_multi(labels, margin_mm=5.0)
        assert len(mock_connection.data) > 0

    def test_print_multi_with_high_resolution(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Test print_multi in high resolution mode."""
        printer = PTE550W(mock_connection)
        labels = [
            Label(sample_image, Tape12mm),
            Label(sample_image, Tape12mm),
        ]
        printer.print_multi(labels, high_resolution=True)
        assert len(mock_connection.data) > 0


def _find_advanced_mode_byte(data: bytes) -> int:
    """Return the mode byte from the ESC i K command in a print payload.

    The ESC i K command is ``1B 69 4B <mode>``. Locates the last
    occurrence (per-page sequences may contain more than one) and
    returns the byte that follows.
    """
    marker = b"\x1b\x69\x4b"
    idx = data.rfind(marker)
    assert idx != -1, "ESC i K not found in payload"
    return data[idx + 3]


def _find_mode_settings_byte(data: bytes) -> int:
    """Return the mode byte from the ESC i M command in a print payload."""
    marker = b"\x1b\x69\x4d"
    idx = data.rfind(marker)
    assert idx != -1, "ESC i M not found in payload"
    return data[idx + 3]


class TestLabelPrinterCapabilityFlags:
    """Test the SUPPORTS_*/DEFAULT_* class attributes for mirror/chain/special-tape."""

    def test_default_capability_flags_on_base_class(self) -> None:
        """LabelPrinter base class declares the new features as supported."""
        from ptouch.printer import LabelPrinter

        assert LabelPrinter.SUPPORTS_MIRROR_PRINT is True
        assert LabelPrinter.SUPPORTS_CHAIN_PRINTING is True
        assert LabelPrinter.SUPPORTS_SPECIAL_TAPE is True

    def test_default_values_on_base_class(self) -> None:
        """LabelPrinter base class defaults the new features to off."""
        from ptouch.printer import LabelPrinter

        assert LabelPrinter.DEFAULT_MIRROR_PRINT is False
        assert LabelPrinter.DEFAULT_CHAIN_PRINTING is False
        assert LabelPrinter.DEFAULT_SPECIAL_TAPE is False

    def test_pte550w_inherits_capability_flags(self) -> None:
        """PTE550W inherits the new capability flags from the base."""
        assert PTE550W.SUPPORTS_MIRROR_PRINT is True
        assert PTE550W.SUPPORTS_CHAIN_PRINTING is True
        assert PTE550W.SUPPORTS_SPECIAL_TAPE is True

    def test_ptp750w_inherits_capability_flags(self) -> None:
        """PTP750W inherits the new capability flags from the base."""
        assert PTP750W.SUPPORTS_MIRROR_PRINT is True
        assert PTP750W.SUPPORTS_CHAIN_PRINTING is True
        assert PTP750W.SUPPORTS_SPECIAL_TAPE is True


class TestCmdAdvancedModeSpecialTape:
    """Test ESC i K bit 4 (special-tape no-cut) handling."""

    @pytest.fixture
    def printer(self, mock_connection: MockConnection) -> PTE550W:
        """Provide a PTE550W instance."""
        return PTE550W(mock_connection)

    def test_special_tape_off_by_default(self, printer: PTE550W) -> None:
        """Bit 4 is clear when special_tape is not passed."""
        cmd = printer._cmd_advanced_mode_settings()
        assert cmd[3] & (1 << 4) == 0

    def test_special_tape_on_sets_bit_4(self, printer: PTE550W) -> None:
        """Bit 4 is set when special_tape=True."""
        cmd = printer._cmd_advanced_mode_settings(special_tape=True)
        assert cmd[:3] == b"\x1b\x69\x4b"
        assert cmd[3] & (1 << 4) != 0

    def test_special_tape_with_half_cut_and_chain(self, printer: PTE550W) -> None:
        """Bits combine without interfering with each other."""
        cmd = printer._cmd_advanced_mode_settings(
            half_cut=True,
            chain_printing=True,
            high_resolution=True,
            special_tape=True,
        )
        # bit 2 = half cut
        assert cmd[3] & (1 << 2) != 0
        # bit 3 = NO chain printing; chain_printing=True clears it
        assert cmd[3] & (1 << 3) == 0
        # bit 4 = special tape
        assert cmd[3] & (1 << 4) != 0
        # bit 6 = high resolution
        assert cmd[3] & (1 << 6) != 0


class TestCmdModeSettingsMirror:
    """Test ESC i M bit 7 (mirror printing) handling."""

    @pytest.fixture
    def printer(self, mock_connection: MockConnection) -> PTE550W:
        """Provide a PTE550W instance."""
        return PTE550W(mock_connection)

    def test_mirror_off_by_default(self, printer: PTE550W) -> None:
        """Bit 7 is clear when mirror_print is not passed."""
        cmd = printer._cmd_mode_settings(auto_cut=True)
        assert cmd[3] & (1 << 7) == 0

    def test_mirror_on_sets_bit_7(self, printer: PTE550W) -> None:
        """Bit 7 is set when mirror_print=True."""
        cmd = printer._cmd_mode_settings(auto_cut=True, mirror_print=True)
        assert cmd[:3] == b"\x1b\x69\x4d"
        assert cmd[3] & (1 << 7) != 0


class TestPrintNewKwargs:
    """Test that print() honors mirror/chain/special_tape kwargs end-to-end."""

    def test_print_with_mirror_sets_bit_7_in_mode(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """print(mirror=True) results in ESC i M bit 7 set in the sent data."""
        printer = PTE550W(mock_connection)
        printer.print(Label(sample_image, Tape12mm), mirror=True)
        mode_byte = _find_mode_settings_byte(mock_connection.data)
        assert mode_byte & (1 << 7) != 0

    def test_print_without_mirror_clears_bit_7(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """print() with no mirror kwarg leaves ESC i M bit 7 clear."""
        printer = PTE550W(mock_connection)
        printer.print(Label(sample_image, Tape12mm))
        mode_byte = _find_mode_settings_byte(mock_connection.data)
        assert mode_byte & (1 << 7) == 0

    def test_print_with_chain_clears_no_chain_bit(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """print(chain=True) clears ESC i K bit 3 (the no-chain bit is INVERTED)."""
        printer = PTE550W(mock_connection)
        printer.print(Label(sample_image, Tape12mm), chain=True)
        mode_byte = _find_advanced_mode_byte(mock_connection.data)
        # bit 3 is "NO chain printing"; chain=True means it should be 0
        assert mode_byte & (1 << 3) == 0

    def test_print_without_chain_sets_no_chain_bit(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """print() with no chain kwarg sets ESC i K bit 3 (feed+cut after page)."""
        printer = PTE550W(mock_connection)
        printer.print(Label(sample_image, Tape12mm))
        mode_byte = _find_advanced_mode_byte(mock_connection.data)
        assert mode_byte & (1 << 3) != 0

    def test_print_with_special_tape_sets_bit_4(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """print(special_tape=True) sets ESC i K bit 4."""
        printer = PTE550W(mock_connection)
        printer.print(Label(sample_image, Tape12mm), special_tape=True)
        mode_byte = _find_advanced_mode_byte(mock_connection.data)
        assert mode_byte & (1 << 4) != 0

    def test_print_without_special_tape_clears_bit_4(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """print() with no special_tape kwarg leaves ESC i K bit 4 clear."""
        printer = PTE550W(mock_connection)
        printer.print(Label(sample_image, Tape12mm))
        mode_byte = _find_advanced_mode_byte(mock_connection.data)
        assert mode_byte & (1 << 4) == 0


class TestPrintDefaultsHonoredFromClass:
    """Test that DEFAULT_* class attrs flow through when kwargs are omitted."""

    def test_subclass_default_mirror_print_true(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """A subclass with DEFAULT_MIRROR_PRINT=True mirrors by default."""

        class MirroredP750W(PTP750W):
            DEFAULT_MIRROR_PRINT: bool = True

        printer = MirroredP750W(mock_connection)
        printer.print(Label(sample_image, Tape12mm))
        mode_byte = _find_mode_settings_byte(mock_connection.data)
        assert mode_byte & (1 << 7) != 0

    def test_runtime_kwarg_overrides_subclass_default(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Explicit mirror=False overrides a subclass DEFAULT_MIRROR_PRINT=True."""

        class MirroredP750W(PTP750W):
            DEFAULT_MIRROR_PRINT: bool = True

        printer = MirroredP750W(mock_connection)
        printer.print(Label(sample_image, Tape12mm), mirror=False)
        mode_byte = _find_mode_settings_byte(mock_connection.data)
        assert mode_byte & (1 << 7) == 0


class TestPrintMultiForwardsNewKwargs:
    """Test that print_multi() forwards mirror/chain/special_tape to print()."""

    def test_print_multi_with_mirror(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """print_multi(mirror=True) sets ESC i M bit 7 on every page."""
        printer = PTE550W(mock_connection)
        labels = [Label(sample_image, Tape12mm), Label(sample_image, Tape12mm)]
        printer.print_multi(labels, mirror=True)
        # Every ESC i M occurrence should have bit 7 set
        data = mock_connection.data
        idx = 0
        marker = b"\x1b\x69\x4d"
        found = 0
        while True:
            idx = data.find(marker, idx)
            if idx == -1:
                break
            assert data[idx + 3] & (1 << 7) != 0
            found += 1
            idx += len(marker)
        assert found >= 2  # one per page

    def test_print_multi_with_chain(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """print_multi(chain=True) clears ESC i K bit 3 on every page."""
        printer = PTE550W(mock_connection)
        labels = [Label(sample_image, Tape12mm), Label(sample_image, Tape12mm)]
        printer.print_multi(labels, chain=True)
        data = mock_connection.data
        idx = 0
        marker = b"\x1b\x69\x4b"
        found = 0
        while True:
            idx = data.find(marker, idx)
            if idx == -1:
                break
            assert data[idx + 3] & (1 << 3) == 0
            found += 1
            idx += len(marker)
        assert found >= 2

    def test_print_multi_with_special_tape(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """print_multi(special_tape=True) sets ESC i K bit 4 on every page."""
        printer = PTE550W(mock_connection)
        labels = [Label(sample_image, Tape12mm), Label(sample_image, Tape12mm)]
        printer.print_multi(labels, special_tape=True)
        data = mock_connection.data
        idx = 0
        marker = b"\x1b\x69\x4b"
        found = 0
        while True:
            idx = data.find(marker, idx)
            if idx == -1:
                break
            assert data[idx + 3] & (1 << 4) != 0
            found += 1
            idx += len(marker)
        assert found >= 2


class TestCapabilityEnforcement:
    """Test that SUPPORTS_* flags are enforced in print()/print_multi()."""

    def test_explicit_unsupported_feature_raises(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Explicitly requesting a feature the model lacks raises ValueError."""

        class NoMirrorP750W(PTP750W):
            SUPPORTS_MIRROR_PRINT = False

        printer = NoMirrorP750W(mock_connection)
        with pytest.raises(ValueError, match="does not support mirror printing"):
            printer.print(Label(sample_image, Tape12mm), mirror=True)
        # No print payload (raster transfer / print command) should be emitted.
        assert b"\x47" not in mock_connection.data  # raster graphics transfer
        assert b"\x1a" not in mock_connection.data and b"\x0c" not in mock_connection.data

    def test_unsupported_default_is_clamped_not_raised(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """A True DEFAULT_* on an unsupported feature is forced off, not raised."""

        class NoMirrorDefaultOnP750W(PTP750W):
            SUPPORTS_MIRROR_PRINT = False
            DEFAULT_MIRROR_PRINT = True

        printer = NoMirrorDefaultOnP750W(mock_connection)
        # No kwarg → default path → must not raise, and bit 7 stays clear.
        printer.print(Label(sample_image, Tape12mm))
        mode_byte = _find_mode_settings_byte(mock_connection.data)
        assert mode_byte & (1 << 7) == 0

    def test_explicit_false_on_unsupported_is_allowed(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """Explicitly disabling an unsupported feature is fine (no raise)."""

        class NoMirrorP750W(PTP750W):
            SUPPORTS_MIRROR_PRINT = False

        printer = NoMirrorP750W(mock_connection)
        printer.print(Label(sample_image, Tape12mm), mirror=False)  # must not raise
        mode_byte = _find_mode_settings_byte(mock_connection.data)
        assert mode_byte & (1 << 7) == 0

    def test_print_multi_half_cut_clamped_for_unsupported(
        self, mock_connection: MockConnection, sample_image: Image.Image
    ) -> None:
        """print_multi() default half_cut clamps to full-cut (no raise) when unsupported."""
        from ptouch.printers import PTP710BT

        printer = PTP710BT(mock_connection)
        labels = [Label(sample_image, Tape12mm), Label(sample_image, Tape12mm)]
        # PTP710BT.SUPPORTS_HALF_CUT is False; the default half_cut=True must
        # clamp rather than raise, and every page's half-cut bit (2) stays clear.
        printer.print_multi(labels)
        data = mock_connection.data
        marker = b"\x1b\x69\x4b"
        idx = 0
        found = 0
        while True:
            idx = data.find(marker, idx)
            if idx == -1:
                break
            assert data[idx + 3] & (1 << 2) == 0
            found += 1
            idx += len(marker)
        assert found >= 2


class TestPrintInformationMediaType:
    """ESC i z: valid flags and the per-family media type for TZe tape."""

    @staticmethod
    def _print_info(printer_cls: type) -> bytes:
        from ptouch import Label, Tape24mm
        from PIL import Image

        conn = MockConnection()
        printer = printer_cls(conn)
        printer.print(Label(Image.new("RGB", (20, 128), "white"), Tape24mm))
        i = conn.data.index(b"\x1biz")
        return conn.data[i + 3 : i + 7]

    def test_e550w_family_sends_laminated(self) -> None:
        """PT-E550W reference: 01h = laminated; 00h would mean no tape."""
        from ptouch import PTE550W, PTP710BT, PTP750W

        for cls in (PTE550W, PTP750W, PTP710BT):
            assert self._print_info(cls) == bytes([0x86, 0x01, 24, 0x00]), cls.__name__

    def test_p900_family_sends_00_for_tape(self) -> None:
        """PT-P900 reference: 00h = laminated/non-laminated tape."""
        from ptouch import PTP900, PTP900W, PTP950NW

        for cls in (PTP900, PTP900W, PTP950NW):
            assert self._print_info(cls)[:2] == bytes([0x86, 0x00]), cls.__name__


class TestStartingPageFlag:
    """ESC i z {n9}: 0 on the first page, 1 on later pages (Brother's sample)."""

    def test_print_multi_marks_later_pages(self) -> None:
        """Every page after the first carries n9 = 1."""
        conn = MockConnection()
        printer = PTE550W(conn)
        labels = [Label(Image.new("RGB", (20, 128), "white"), Tape24mm) for _ in range(3)]
        printer.print_multi(labels)
        flags = []
        start = 0
        while (i := conn.data.find(b"\x1biz", start)) != -1:
            flags.append(conn.data[i + 3 + 8])
            start = i + 1
        assert flags == [0, 1, 1]

    def test_single_print_is_a_starting_page(self) -> None:
        """A single print() is the first page of its job."""
        conn = MockConnection()
        printer = PTE550W(conn)
        printer.print(Label(Image.new("RGB", (20, 128), "white"), Tape24mm))
        i = conn.data.index(b"\x1biz")
        assert conn.data[i + 3 + 8] == 0


class TestInvalidateLength:
    """Invalidate preamble length per model family, from each raster reference."""

    def test_e550w_family_sends_100(self) -> None:
        """PT-E550W/P750W/P710BT reference: 100 bytes."""
        from ptouch import PTP710BT, PTP750W

        for cls in (PTE550W, PTP750W, PTP710BT):
            conn = MockConnection()
            cls(conn)
            assert conn.data == b"\x00" * 100 + b"\x1b@", cls.__name__

    def test_p900_family_sends_200(self) -> None:
        """PT-P900 series reference: 200 bytes."""
        conn = MockConnection()
        PTP900(conn)
        assert conn.data == b"\x00" * 200 + b"\x1b@"


class TestHalfCutDefault:
    """Half cut only where it separates labels: strips, not single labels."""

    @staticmethod
    def _advanced_modes(data: bytes) -> list[int]:
        out, start = [], 0
        while (i := data.find(b"\x1biK", start)) != -1:
            out.append(data[i + 3])
            start = i + 1
        return out

    def test_single_label_has_no_half_cut(self) -> None:
        """A single print() sends ESC i K 08 (no chain, no half cut)."""
        conn = MockConnection()
        PTE550W(conn).print(Label(Image.new("RGB", (20, 128), "white"), Tape24mm))
        assert self._advanced_modes(conn.data) == [0x08]

    def test_strip_keeps_half_cut(self) -> None:
        """print_multi() still half-cuts between labels (ESC i K 0C)."""
        conn = MockConnection()
        labels = [Label(Image.new("RGB", (20, 128), "white"), Tape24mm) for _ in range(2)]
        PTE550W(conn).print_multi(labels)
        assert self._advanced_modes(conn.data) == [0x0C, 0x0C]

    def test_explicit_half_cut_still_possible(self) -> None:
        """Callers can still ask for a half cut on a single label."""
        conn = MockConnection()
        PTE550W(conn).print(Label(Image.new("RGB", (20, 128), "white"), Tape24mm), half_cut=True)
        assert self._advanced_modes(conn.data) == [0x0C]


class TestE550WVerifiedJobs:
    """Command sequences printed and checked on a real PT-E550W.

    Verified 2026-10-06: PT-E550W, main firmware FP-MAIN 1.31, TZe-S251
    (24 mm). The single label printed with a full cut at the end; the
    two-label strip came out as one piece (lead, half cut, label, half
    cut, label, full cut). Image content does not matter for these
    settings, so a plain test image is used. Changing any expected
    command below needs a new hardware check (see README).
    """

    @staticmethod
    def _label(width: int = 84) -> Label:
        # A busy pattern, so raster lines need both PackBits runs and the
        # 17-byte literal fallback.
        image = Image.new("RGB", (width, 128), "white")
        for x in range(width):
            for y in range(128):
                if (x * 7 + y * 3 + (x * y) % 5) % 4 < 2:
                    image.putpixel((x, y), (0, 0, 0))
        return Label(image, Tape24mm)

    @staticmethod
    def _hires_page(
        z_lines: str, page: int, mode: str, cut_each: str | None, k: str
    ) -> list[tuple[str, str]]:
        """One high-resolution page header (360 dpi image, margin 28)."""
        return [
            ("ESC i a", "01"),
            ("ESC i z", f"86 01 18 00 {z_lines} 00 00 00 {page:02x} 00"),
            ("ESC i M", mode),
            *([("ESC i A", cut_each)] if cut_each else []),
            ("ESC i K", k),
            ("ESC i d", "1c 00"),  # 28 dots = 2 mm at 360 dpi
            ("compression", "02"),
        ]

    def test_free_hard_cuts_h1(self, mock_connection: MockConnection) -> None:
        """H1: pieces of 2, 1 and 3 labels as three chained jobs, high resolution.

        Verified 2026-10-06: one lead for the whole run, full cuts exactly
        after labels 2, 3 and 6, half cuts inside the pieces. Every page of
        a job has auto cut, half cut and cut each = piece size; all jobs
        but the last are chained (K 44), the last is not (K 4c). The labels
        were 180 columns at 360 dpi.
        """
        printer = PTE550W(mock_connection)
        pieces = [2, 1, 3]
        jobs = [
            printer.build_job(
                [self._label(180) for _ in range(n)],
                cut_each=n,
                chain=i < len(pieces) - 1,
                half_cut=True,
                auto_cut=True,
                high_resolution_image=True,
            )
            for i, n in enumerate(pieces)
        ]
        raster = ("raster", "180 lines, all blocks <= 17 bytes")
        assert job_commands(jobs[0]) == [
            *self._hires_page("b4", 0, "40", "02", "44"),  # chain + half cut + high res
            raster,
            ("print", "0c"),
            *self._hires_page("b4", 1, "40", "02", "44"),
            raster,
            ("print + feed", "1a"),
        ]
        assert job_commands(jobs[1]) == [
            *self._hires_page("b4", 0, "40", "01", "44"),
            raster,
            ("print + feed", "1a"),
        ]
        assert job_commands(jobs[2]) == [
            *self._hires_page("b4", 0, "40", "03", "4c"),  # last job: no chain
            raster,
            ("print", "0c"),
            *self._hires_page("b4", 1, "40", "03", "4c"),
            raster,
            ("print", "0c"),
            *self._hires_page("b4", 1, "40", "03", "4c"),
            raster,
            ("print + feed", "1a"),
        ]

    def test_high_resolution_strip_mid(self, mock_connection: MockConnection) -> None:
        """The MID asset label strip: two 205-column labels, half cuts, auto cut off.

        Verified 2026-10-06 (asset label WZ00042 and a user label in one
        strip): one piece, half cut between the labels, full cut at the end.
        """
        job = PTE550W(mock_connection).build_job(
            [self._label(205), self._label(205)],
            auto_cut=False,
            half_cut=True,
            high_resolution_image=True,
        )
        raster = ("raster", "205 lines, all blocks <= 17 bytes")
        assert job_commands(job) == [
            *self._hires_page("cd", 0, "00", None, "4c"),
            raster,
            ("print", "0c"),
            *self._hires_page("cd", 1, "00", None, "4c"),
            raster,
            ("print + feed", "1a"),
        ]

    def test_single_label(self, mock_connection: MockConnection) -> None:
        """One label: auto cut, cut each label, no half cut, feed at the end."""
        PTE550W(mock_connection).print(self._label())
        assert job_commands(mock_connection.data) == [
            ("invalidate", "100 x 00"),
            ("initialize", "1b 40"),
            ("ESC i a", "01"),  # raster mode
            ("ESC i z", "86 01 18 00 54 00 00 00 00 00"),  # laminated, 24 mm, 84 lines, page 0
            ("ESC i M", "40"),  # auto cut
            ("ESC i A", "01"),  # cut each label
            ("ESC i K", "08"),  # no chain printing
            ("ESC i d", "0e 00"),  # 14-dot margin
            ("compression", "02"),  # TIFF / PackBits
            ("raster", "84 lines, all blocks <= 17 bytes"),
            ("print + feed", "1a"),
        ]

    def test_half_cut_strip(self, mock_connection: MockConnection) -> None:
        """Two labels: auto cut off, half cut, later page marked, one feed."""
        PTE550W(mock_connection).print_multi([self._label(), self._label()])
        page = [
            ("ESC i M", "00"),  # auto cut off: half cuts between labels
            ("ESC i K", "0c"),  # half cut + no chain printing
            ("ESC i d", "0e 00"),
            ("compression", "02"),
            ("raster", "84 lines, all blocks <= 17 bytes"),
        ]
        assert job_commands(mock_connection.data) == [
            ("invalidate", "100 x 00"),
            ("initialize", "1b 40"),
            ("ESC i a", "01"),
            ("ESC i z", "86 01 18 00 54 00 00 00 00 00"),  # starting page
            *page,
            ("print", "0c"),
            ("ESC i a", "01"),
            ("ESC i z", "86 01 18 00 54 00 00 00 01 00"),  # later page
            *page,
            ("print + feed", "1a"),
        ]


def _page_commands(data: bytes, name: str) -> list[str]:
    """Values of one command over all pages of a job."""
    return [value for cmd, value in job_commands(data) if cmd == name]


class TestCutEach:
    """build_page(cut_each=N): full cut after every N labels (ESC i A n)."""

    @staticmethod
    def _label() -> Label:
        return Label(Image.new("RGB", (20, 128), "white"), Tape24mm)

    def test_default_is_one(self, mock_connection: MockConnection) -> None:
        """Without cut_each, auto-cut pages keep ESC i A 01."""
        page = PTE550W(mock_connection).build_page(self._label(), auto_cut=True)
        assert _page_commands(page, "ESC i A") == ["01"]

    @pytest.mark.parametrize("n", [2, 3, 55, 99])
    def test_sets_count(self, mock_connection: MockConnection, n: int) -> None:
        """The value is sent as the single byte of ESC i A."""
        page = PTE550W(mock_connection).build_page(self._label(), auto_cut=True, cut_each=n)
        assert _page_commands(page, "ESC i A") == [f"{n:02x}"]

    @pytest.mark.parametrize("n", [0, 100, -1])
    def test_out_of_range(self, mock_connection: MockConnection, n: int) -> None:
        """The raster reference allows 1-99."""
        with pytest.raises(ValueError, match="between 1 and 99"):
            PTE550W(mock_connection).build_page(self._label(), auto_cut=True, cut_each=n)

    def test_not_an_integer(self, mock_connection: MockConnection) -> None:
        """Booleans and floats are refused, not truncated."""
        printer = PTE550W(mock_connection)
        for bad in (True, 2.0):
            with pytest.raises(ValueError, match="integer"):
                printer.build_page(self._label(), auto_cut=True, cut_each=bad)  # type: ignore[arg-type]

    def test_needs_auto_cut(self, mock_connection: MockConnection) -> None:
        """ESC i A is only sent with auto cut, so cut_each > 1 without it is an error."""
        with pytest.raises(ValueError, match="auto cut"):
            PTE550W(mock_connection).build_page(self._label(), auto_cut=False, cut_each=2)

    def test_one_without_auto_cut_is_fine(self, mock_connection: MockConnection) -> None:
        """The default stays valid on strips (auto cut off, no ESC i A)."""
        page = PTE550W(mock_connection).build_page(self._label(), auto_cut=False)
        assert _page_commands(page, "ESC i A") == []


class TestChainedPage:
    """build_page(chain=True): ESC i K without the no-chain bit (0x08)."""

    @staticmethod
    def _label() -> Label:
        return Label(Image.new("RGB", (20, 128), "white"), Tape24mm)

    def test_chained_page_clears_bit_3(self, mock_connection: MockConnection) -> None:
        """Chain, half cut, auto cut: K = 04 (half cut only)."""
        page = PTE550W(mock_connection).build_page(
            self._label(), auto_cut=True, half_cut=True, chain=True
        )
        (k,) = _page_commands(page, "ESC i K")
        assert int(k, 16) & 0x08 == 0
        assert k == "04"

    def test_unchained_page_sets_bit_3(self, mock_connection: MockConnection) -> None:
        """The same page without chain: K = 0c."""
        page = PTE550W(mock_connection).build_page(
            self._label(), auto_cut=True, half_cut=True, chain=False
        )
        assert _page_commands(page, "ESC i K") == ["0c"]

    def test_chained_page_still_ends_with_feed(self, mock_connection: MockConnection) -> None:
        """Chain only drops the final cut; the last page still ends with 1A."""
        page = PTE550W(mock_connection).build_page(self._label(), chain=True, feed=True)
        assert job_commands(page)[-1] == ("print + feed", "1a")


class TestHighResolutionImage:
    """build_page(high_resolution_image=True): a 360 dpi image, each line once."""

    @staticmethod
    def _label(width: int = 205) -> Label:
        image = Image.new("RGB", (width, 128), "white")
        for x in range(0, width, 2):
            for y in range(x % 7, 128, 5):
                image.putpixel((x, y), (0, 0, 0))
        return Label(image, Tape24mm)

    def test_commands(self, mock_connection: MockConnection) -> None:
        """K bit 0x40, margin 28 dots, as many lines as the image is wide."""
        page = PTE550W(mock_connection).build_page(self._label(), high_resolution_image=True)
        assert job_commands(page) == [
            ("ESC i a", "01"),
            ("ESC i z", "86 01 18 00 cd 00 00 00 00 00"),  # 205 lines, not 410
            ("ESC i M", "40"),
            ("ESC i A", "01"),
            ("ESC i K", "48"),  # no chain + high resolution
            ("ESC i d", "1c 00"),  # 28 dots = 2 mm at 360 dpi
            ("compression", "02"),
            ("raster", "205 lines, all blocks <= 17 bytes"),
            ("print + feed", "1a"),
        ]

    def test_same_lines_as_normal_page(self, mock_connection: MockConnection) -> None:
        """Only K and the margin differ from the normal-resolution page.

        This is how the high-resolution labels verified on a PT-E550W
        (2026-10-06) were made: a normal page with K | 0x40 and the
        margin doubled, patched into the bytes.
        """
        printer = PTE550W(mock_connection)
        normal = printer.build_page(self._label(), half_cut=True, auto_cut=False)
        patched = normal.replace(b"\x1biK\x0c", b"\x1biK\x4c").replace(
            b"\x1bid\x0e\x00", b"\x1bid\x1c\x00"
        )
        hires = printer.build_page(
            self._label(), half_cut=True, auto_cut=False, high_resolution_image=True
        )
        assert hires == patched

    def test_repeating_mode_unchanged(self, mock_connection: MockConnection) -> None:
        """high_resolution=True still repeats every line of a normal image."""
        page = PTE550W(mock_connection).build_page(self._label(100), high_resolution=True)
        commands = dict(job_commands(page))
        assert commands["ESC i z"] == "86 01 18 00 c8 00 00 00 00 00"  # 200 lines
        assert commands["ESC i K"] == "48"
        assert commands["ESC i d"] == "1c 00"
        assert commands["raster"] == "200 lines, all blocks <= 17 bytes"

    def test_validates(self, mock_connection: MockConnection) -> None:
        """The validator reads the page as high resolution with a 28-dot margin."""
        from ptouch.validate import validate_job

        printer = PTE550W(mock_connection)
        summary = validate_job(
            printer.build_page(self._label(), high_resolution_image=True), printer
        )
        (page,) = summary.pages
        assert page.high_resolution and page.margin_dots == 28 and page.raster_lines == 205

    def test_conflicting_flags(self, mock_connection: MockConnection) -> None:
        """A 360 dpi image cannot be sent in normal resolution."""
        with pytest.raises(ValueError, match="needs high resolution"):
            PTE550W(mock_connection).build_page(
                self._label(), high_resolution=False, high_resolution_image=True
            )

    def test_printer_without_high_resolution(self, mock_connection: MockConnection) -> None:
        """Models without a high resolution refuse the image."""

        class NoHighResolution(PTE550W):
            RESOLUTION_DPI_HIGH = 0

        printer = NoHighResolution(mock_connection)
        with pytest.raises(ValueError, match="does not support high resolution"):
            printer.build_page(self._label(), high_resolution_image=True)


class TestBuildJob:
    """build_job: a whole job, the same settings on every page."""

    @staticmethod
    def _labels(n: int) -> list[Label]:
        return [Label(Image.new("RGB", (20, 128), "white"), Tape24mm) for _ in range(n)]

    def test_preamble(self, mock_connection: MockConnection) -> None:
        """Invalidate (100 x 00 on the E550W) and ESC @, as written on connect."""
        printer = PTE550W(mock_connection)
        assert printer.preamble() == b"\x00" * 100 + b"\x1b@"
        assert mock_connection.data == printer.preamble()

    def test_job_has_no_preamble(self, mock_connection: MockConnection) -> None:
        """The job starts at the first page's ESC i a."""
        job = PTE550W(mock_connection).build_job(self._labels(1))
        assert job.startswith(b"\x1bia\x01")

    def test_cut_each_job(self, mock_connection: MockConnection) -> None:
        """Four labels, cut each 2, half cut: identical pages, one final feed."""
        job = PTE550W(mock_connection).build_job(self._labels(4), cut_each=2, half_cut=True)
        page = [
            ("ESC i M", "40"),
            ("ESC i A", "02"),
            ("ESC i K", "0c"),
            ("ESC i d", "0e 00"),
            ("compression", "02"),
            ("raster", "20 lines, all blocks <= 17 bytes"),
        ]
        later = [("ESC i a", "01"), ("ESC i z", "86 01 18 00 14 00 00 00 01 00"), *page]
        assert job_commands(job) == [
            ("ESC i a", "01"),
            ("ESC i z", "86 01 18 00 14 00 00 00 00 00"),
            *page,
            ("print", "0c"),
            *later,
            ("print", "0c"),
            *later,
            ("print", "0c"),
            *later,
            ("print + feed", "1a"),
        ]

    def test_chain_on_every_page(self, mock_connection: MockConnection) -> None:
        """A chained job clears the no-chain bit on every page, not just the last."""
        job = PTE550W(mock_connection).build_job(self._labels(3), half_cut=True, chain=True)
        assert _page_commands(job, "ESC i K") == ["04", "04", "04"]
        assert job_commands(job)[-1] == ("print + feed", "1a")

    def test_not_a_multiple(self, mock_connection: MockConnection) -> None:
        """Three labels cannot be cut in pieces of two."""
        with pytest.raises(ValueError, match="3 labels is not a multiple of cut_each 2"):
            PTE550W(mock_connection).build_job(self._labels(3), cut_each=2)

    def test_empty(self, mock_connection: MockConnection) -> None:
        """A job needs a label."""
        with pytest.raises(ValueError, match="At least one label"):
            PTE550W(mock_connection).build_job([])

    def test_mixed_tapes(self, mock_connection: MockConnection) -> None:
        """All pages are on the same tape."""
        labels = [*self._labels(1), Label(Image.new("RGB", (20, 70), "white"), Tape12mm)]
        with pytest.raises(ValueError, match="same tape"):
            PTE550W(mock_connection).build_job(labels)

    def test_max_pages(self, mock_connection: MockConnection) -> None:
        """printer.max_pages caps build_job like send_job."""
        from ptouch.validate import InvalidJobError

        printer = PTE550W(mock_connection)
        printer.max_pages = 2
        with pytest.raises(InvalidJobError, match="more than 2 pages"):
            printer.build_job(self._labels(3))


class TestPT2730:
    """PT-2730 model attributes (see printers.py for the sources)."""

    def test_usb_product_id(self) -> None:
        """04F9:2041 as in ptouch-print's device table and usb.ids."""
        assert PT2730.USB_PRODUCT_ID == 0x2041

    def test_head(self) -> None:
        """128-dot, 180 dpi head, no high resolution."""
        assert PT2730.TOTAL_PINS == 128
        assert PT2730.BYTES_PER_LINE == 16
        assert PT2730.RESOLUTION_DPI == 180
        assert PT2730.RESOLUTION_DPI_HIGH == 0

    def test_capabilities(self, mock_connection: MockConnection) -> None:
        """Legacy commands: cutter and chain; no half cut, cut-each, special tape."""
        printer = PT2730(mock_connection)
        assert printer.LEGACY_COMMANDS
        assert not printer.supports_high_resolution
        assert not printer.SUPPORTS_HALF_CUT
        assert not printer.SUPPORTS_PAGE_NUMBER_CUTS
        assert not printer.SUPPORTS_SPECIAL_TAPE
        assert printer.SUPPORTS_AUTO_CUT and printer.SUPPORTS_CHAIN_PRINTING
        assert printer.use_compression is False

    def test_measured_tape_use(self) -> None:
        """Lead, tail, per-label feed, feed scale: PROVISIONAL (one sample, 2026-10-07)."""
        assert PT2730.LEAD_MM == 24.5
        assert PT2730.TAIL_MM == 0.5
        assert PT2730.FEED_PER_LABEL_MM == 5.0
        assert PT2730.FEED_SCALE == pytest.approx(1.029, abs=0.001)

    def test_feed_scale_helpers(self, mock_connection: MockConnection) -> None:
        """The ruler: dot 423 (59.7 mm nominal) printed at 58 mm."""
        printer = PT2730(mock_connection)
        assert printer.printed_length_mm(423) == pytest.approx(58.0, abs=0.05)
        assert printer.raster_lines_for_mm(60) == 438
        assert printer.printed_length_mm(438) == pytest.approx(60.0, abs=0.1)
        # Models without a measured correction: nominal resolution.
        assert PTE550W(MockConnection()).raster_lines_for_mm(60) == 425
        assert PTE550W.FEED_SCALE == 1.0

    def test_stretch_for_feed(self, mock_connection: MockConnection) -> None:
        """Opt-in stretch along the tape; height and other models unchanged."""
        image = Image.new("1", (425, 128), 1)
        stretched = PT2730(mock_connection).stretch_for_feed(image)
        assert stretched.size == (437, 128)
        assert PTE550W(MockConnection()).stretch_for_feed(image) is image

    def test_tapes_up_to_24mm(self, mock_connection: MockConnection) -> None:
        """TZe 3.5 to 24 mm; no 36 mm, no heat shrink tube."""
        printer = PT2730(mock_connection)
        assert [t.__name__ for t in printer.supported_tapes] == [
            "Tape12mm", "Tape18mm", "Tape24mm", "Tape3_5mm", "Tape6mm", "Tape9mm",
        ]  # fmt: skip
        with pytest.raises(ValueError, match="not supported"):
            printer.get_tape_config(Tape36mm())


class TestPT2730Refusals:
    """What the PT-2730 cannot be told is an error, not silently dropped."""

    def test_compression_refused(self, mock_connection: MockConnection) -> None:
        """No M command: compression raises, before anything is sent."""
        with pytest.raises(ValueError, match="compression"):
            PT2730(mock_connection, use_compression=True)
        assert mock_connection.data == b""
        printer = PT2730(mock_connection)
        printer.use_compression = True
        with pytest.raises(ValueError, match="compression"):
            printer.build_page(TestPT2730Jobs._label())

    def test_high_resolution_refused(self, mock_connection: MockConnection) -> None:
        """No high resolution, whichever way it is asked for."""
        with pytest.raises(ValueError, match="high resolution"):
            PT2730(mock_connection, high_resolution=True)
        printer = PT2730(mock_connection)
        with pytest.raises(ValueError, match="high resolution"):
            printer.build_page(TestPT2730Jobs._label(), high_resolution=True)
        with pytest.raises(ValueError, match="high resolution"):
            printer.build_page(TestPT2730Jobs._label(), high_resolution_image=True)

    def test_margin_refused(self, mock_connection: MockConnection) -> None:
        """No ESC i d: an explicit margin raises."""
        printer = PT2730(mock_connection)
        with pytest.raises(ValueError, match="margin"):
            printer.build_page(TestPT2730Jobs._label(), margin_mm=2.0)
        with pytest.raises(ValueError, match="margin"):
            printer.build_job([TestPT2730Jobs._label()], margin_mm=2.0)

    def test_cut_options_refused(self, mock_connection: MockConnection) -> None:
        """No ESC i A (cut each), no half cut, no special-tape bit."""
        printer = PT2730(mock_connection)
        label = TestPT2730Jobs._label()
        with pytest.raises(ValueError, match="cut_each"):
            printer.build_job([label, label], cut_each=2)
        with pytest.raises(ValueError, match="half-cut"):
            printer.build_page(label, half_cut=True)
        with pytest.raises(ValueError, match="special-tape"):
            printer.build_page(label, special_tape=True)

    def test_precut_refused(self, mock_connection: MockConnection) -> None:
        """The precut sequence needs ESC i z and ESC i d."""
        printer = PT2730(mock_connection)
        with pytest.raises(ValueError, match="precut"):
            printer.precut(Tape24mm())

    def test_validator_refuses_newer_commands(self, mock_connection: MockConnection) -> None:
        """A PT-E550W-style job (the one that hung the PT-2730) does not validate."""
        from ptouch.validate import InvalidJobError, validate_job

        e550w = PTE550W(MockConnection(), use_compression=False)
        job = e550w.build_job([TestPT2730Jobs._label()])
        with pytest.raises(InvalidJobError, match="ESC i R 01"):
            validate_job(job, PT2730(mock_connection))
        header = b"\x1biR\x01\x1biM\x40"
        line = b"G\x10\x00" + b"\xff" * 16
        for bad in (
            header + b"\x1bid\x0e\x00" + line + b"\x1a",  # margin
            header + b"M\x00" + line + b"\x1a",  # compression
            header + b"\x1biK\x08\x1biK\x08" + line + b"\x1a",  # K twice
            b"\x1biR\x01\x1biK\x08" + line + b"\x1a",  # K without auto cut
            header + line + b"\x0c" + b"\x1biM\x40" + line + b"\x1a",  # header again
            header + b"Z" + b"\x1a",  # zero line
            header + b"\x1a",  # no lines
            header + line + b"\x0c",  # no 1A
        ):
            with pytest.raises(InvalidJobError):
                validate_job(bad, PT2730(MockConnection()))


class TestPT2730Jobs:
    """Command sequences the PT-2730 gets (legacy command set).

    Verified on hardware 2026-10-07 (PT-2730 over /dev/usb/lp0, 24 mm TZe
    laminated): ESC i R 01 + lines + 1A prints; adding ESC i M 40 cuts
    cleanly; ESC i R 01, ESC i M 40, ESC i K 08, page, 0C, page, 1A gives
    separately cut labels; the same pages without M and K one uncut piece.
    The PT-E550W sequence (ESC i a, z, M, A, K, d, M 00) hung the printer.
    Changing a verified sequence needs a new hardware check; update the
    README's "Verified on hardware" table too.
    """

    @staticmethod
    def _label(width: int = 84) -> Label:
        image = Image.new("RGB", (width, 128), "white")
        for x in range(0, width, 3):
            for y in range(128):
                image.putpixel((x, y), (0, 0, 0))
        return Label(image, Tape24mm)

    PREAMBLE = [("invalidate", "100 x 00"), ("initialize", "1b 40")]
    LINES = ("raster", "84 lines, uncompressed")

    def test_single_label_cut(self, mock_connection: MockConnection) -> None:
        """One cut label: R 01 + M 40 (verified to cut cleanly) + K 08.

        K 08 as in the verified two-label job (cut after the last label).
        """
        PT2730(mock_connection).print(self._label())
        assert job_commands(mock_connection.data, compressed=False) == [
            *self.PREAMBLE,
            ("ESC i R", "01"),  # raster mode (legacy)
            ("ESC i M", "40"),  # auto cut
            ("ESC i K", "08"),  # no chain: feed and cut after the last label
            self.LINES,
            ("print + feed", "1a"),
        ]

    def test_two_labels_cut_each(self, mock_connection: MockConnection) -> None:
        """Verified: two separately cut labels, header once, 0C between."""
        printer = PT2730(mock_connection)
        job = printer.build_job([self._label(), self._label()])
        assert job_commands(job, compressed=False) == [
            ("ESC i R", "01"),
            ("ESC i M", "40"),
            ("ESC i K", "08"),
            self.LINES,
            ("print", "0c"),
            self.LINES,
            ("print + feed", "1a"),
        ]

    def test_print_multi_is_the_same_job(self, mock_connection: MockConnection) -> None:
        """print_multi falls back to full cuts (no half cut): the same bytes."""
        printer = PT2730(mock_connection)
        printer.print_multi([self._label(), self._label()])
        sent = mock_connection.data[len(printer.preamble()) :]
        assert sent == printer.build_job([self._label(), self._label()])

    def test_no_cut(self, mock_connection: MockConnection) -> None:
        """Verified: without M and K the labels come out as one uncut piece."""
        printer = PT2730(mock_connection)
        job = printer.build_job([self._label(), self._label()], auto_cut=False)
        assert job_commands(job, compressed=False) == [
            ("ESC i R", "01"),
            self.LINES,
            ("print", "0c"),
            self.LINES,
            ("print + feed", "1a"),
        ]

    def test_chained_job(self, mock_connection: MockConnection) -> None:
        """Chain: auto cut without K 08. NOT yet verified on hardware.

        The uncut two-label job that was verified had neither M nor K.
        """
        printer = PT2730(mock_connection)
        job = printer.build_job([self._label(), self._label()], chain=True)
        assert job_commands(job, compressed=False) == [
            ("ESC i R", "01"),
            ("ESC i M", "40"),
            self.LINES,
            ("print", "0c"),
            self.LINES,
            ("print + feed", "1a"),
        ]

    def test_mirror(self, mock_connection: MockConnection) -> None:
        """Mirror sets ESC i M bit 7. NOT yet verified on hardware."""
        printer = PT2730(mock_connection)
        page = printer.build_page(self._label(), mirror=True)
        assert job_commands(page, compressed=False)[:3] == [
            ("ESC i R", "01"),
            ("ESC i M", "c0"),
            ("ESC i K", "08"),
        ]

    def test_raster_lines(self, mock_connection: MockConnection) -> None:
        """Every line is G 10 00 and 16 plain bytes, as sent on hardware."""
        job = PT2730(mock_connection).build_job([self._label()], auto_cut=False)
        lines = job[4:-1]
        assert len(lines) == 84 * 19
        assert all(lines[i : i + 3] == b"G\x10\x00" for i in range(0, len(lines), 19))
        assert lines[3:19] == b"\xff" * 16  # column 0 is black on all 128 pins

    def test_jobs_validate(self, mock_connection: MockConnection) -> None:
        """The validator reads the legacy grammar, page by page."""
        printer = PT2730(mock_connection)
        summary = printer.send_job(printer.build_job([self._label()] * 3))
        assert [p.compressed for p in summary.pages] == [False] * 3
        assert [p.auto_cut for p in summary.pages] == [True] * 3
        assert [p.chain for p in summary.pages] == [False] * 3
        assert [p.last for p in summary.pages] == [False, False, True]
        assert summary.raster_lines == 3 * 84
