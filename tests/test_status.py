# SPDX-FileCopyrightText: 2026 Marius Alwan Meyer
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for the status block and the SNMP reader."""

import socket
import threading

import pytest

from ptouch.snmp import STATUS_OID, SnmpError, build_get, parse_get_response, read_status
from ptouch.status import Error1, Error2, StatusError, parse_status

# Status blocks read from a PT-E550W (firmware 1.31) over SNMP on 2026-10-06.
S251 = bytes.fromhex(
    "80 20 42 30 66 30 04 00 00 00 18 01 00 00 00 4000 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00"
)
FX251 = bytes.fromhex(
    "80 20 42 30 66 30 04 00 00 00 18 01 00 00 00 4000 00 00 00 00 00 00 00 90 08 00 00 00 00 00 00"
)


class TestParseStatus:
    """Decoding the 32-byte block."""

    def test_s251(self) -> None:
        """24 mm laminated, black on white: TZe-S251 (or plain TZe-251)."""
        s = parse_status(S251)
        assert s.model == "PT-E550W"
        assert s.media_width_mm == 24 and s.media_type == 0x01
        assert s.tape_color == 0x01 and s.text_color == 0x08
        assert s.tape == "24 mm laminated tape, black on white"
        assert not s.has_error and s.errors == []
        assert s.has_media and not s.is_printing

    def test_fx251_reports_flexible_id_tape(self) -> None:
        """TZe-FX251 differs only in the tape colour: white (flexible ID)."""
        s = parse_status(FX251)
        assert s.tape_color == 0x90
        assert s.tape == "24 mm laminated tape, black on white (flexible ID)"

    def test_error_bits(self) -> None:
        """Error bits are decoded per table (1) and (2)."""
        block = bytearray(S251)
        block[8] = 0x04 | 0x08  # cutter jam, weak batteries
        block[9] = 0x10  # cover open
        s = parse_status(bytes(block))
        assert s.has_error
        assert s.error1 == Error1.CUTTER_JAM | Error1.WEAK_BATTERIES
        assert s.error2 == Error2.COVER_OPEN
        assert s.errors == ["cutter jam", "weak batteries", "cover open"]

    def test_unused_bits_are_ignored(self) -> None:
        """Bits the reference marks as not used do not count as errors."""
        block = bytearray(S251)
        block[8] = 0x02
        block[9] = 0x40
        assert not parse_status(bytes(block)).has_error

    def test_no_tape(self) -> None:
        """Media type 00 / width 0 means no cassette."""
        block = bytearray(S251)
        block[10] = 0
        block[11] = 0
        s = parse_status(bytes(block))
        assert not s.has_media and s.tape == "no tape"

    def test_printing_phase(self) -> None:
        """Phase type 01 is the printing state."""
        block = bytearray(S251)
        block[19] = 0x01
        assert parse_status(bytes(block)).is_printing

    @pytest.mark.parametrize("data", [S251[:31], b"\x00" * 32, b"\x81" + S251[1:]])
    def test_rejects_non_status(self, data: bytes) -> None:
        """Wrong length or header is not a status block."""
        with pytest.raises(StatusError):
            parse_status(data)


def _get_response(value_tag: int, value: bytes, error_status: int = 0) -> bytes:
    """Build a minimal SNMPv1 GetResponse for tests."""
    from ptouch.snmp import _integer, _oid, _tlv

    varbind = _tlv(0x30, _tlv(0x30, _oid(STATUS_OID) + _tlv(value_tag, value)))
    pdu = _tlv(0xA2, _integer(1) + _integer(error_status) + _integer(0) + varbind)
    return _tlv(0x30, _integer(0) + _tlv(0x04, b"public") + pdu)


class TestSnmp:
    """The minimal SNMPv1 client."""

    def test_get_request_encoding(self) -> None:
        """GetRequest: version 0, community, PDU A0, OID, NULL value."""
        msg = build_get(STATUS_OID)
        assert msg[0] == 0x30
        assert b"\x04\x06public" in msg
        assert b"\xa0" in msg
        assert bytes.fromhex("2b 06 01 04 01 93 03 03 03 09 01 06 01 00".replace(" ", "")) in msg

    def test_parse_response_value(self) -> None:
        """The varbind's octet string comes back as bytes."""
        assert parse_get_response(_get_response(0x04, S251)) == S251

    def test_parse_response_errors(self) -> None:
        """Error status and noSuchObject raise SnmpError."""
        with pytest.raises(SnmpError):
            parse_get_response(_get_response(0x04, S251, error_status=2))
        with pytest.raises(SnmpError):
            parse_get_response(_get_response(0x80, b""))
        with pytest.raises(SnmpError):
            parse_get_response(b"\x30\x05\x02")

    def test_read_status_over_udp(self) -> None:
        """End to end against a local UDP responder."""
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.bind(("127.0.0.1", 0))
        port = server.getsockname()[1]

        def serve() -> None:
            _, addr = server.recvfrom(4096)
            server.sendto(_get_response(0x04, S251), addr)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        status = read_status("127.0.0.1", timeout=2, port=port)
        thread.join(1)
        server.close()
        assert status.tape == "24 mm laminated tape, black on white"

    def test_read_status_timeout(self) -> None:
        """No answer raises SnmpError instead of hanging."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as silent:
            silent.bind(("127.0.0.1", 0))  # a port that never answers
            with pytest.raises(SnmpError):
                read_status("127.0.0.1", timeout=0.2, port=silent.getsockname()[1])
