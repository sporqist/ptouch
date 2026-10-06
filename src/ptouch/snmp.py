# SPDX-FileCopyrightText: 2026 Marius Alwan Meyer
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Read the status of a network printer over SNMP.

Network P-touch models never answer on the raw print port (9100), so
``ESC i S`` gets no reply there. They do publish the same 32-byte status
block over SNMP (v1, community ``public``) under Brother's enterprise
OID ``1.3.6.1.4.1.2435.3.3.9.1.6.1.0``. Verified on a PT-E550W
(firmware 1.31): the block tracks the loaded cassette.

This is a minimal SNMPv1 GET client (a few BER encoders) so the library
needs no SNMP dependency. It only reads.
"""

import socket

from .status import PrinterStatus, parse_status

STATUS_OID = "1.3.6.1.4.1.2435.3.3.9.1.6.1.0"


class SnmpError(OSError):
    """No usable SNMP answer."""


def _length(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(body)]) + body


def _tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + _length(len(value)) + value


def _integer(n: int) -> bytes:
    return _tlv(0x02, n.to_bytes(max(1, (n.bit_length() + 8) // 8), "big", signed=True))


def _oid(dotted: str) -> bytes:
    parts = [int(p) for p in dotted.split(".")]
    body = bytes([40 * parts[0] + parts[1]])
    for n in parts[2:]:
        chunk = [n & 0x7F]
        n >>= 7
        while n:
            chunk.append(0x80 | (n & 0x7F))
            n >>= 7
        body += bytes(reversed(chunk))
    return _tlv(0x06, body)


def _read(buf: bytes, i: int) -> tuple[int, bytes, int]:
    """Read one TLV at i; return (tag, value, next index)."""
    if i + 2 > len(buf):
        raise SnmpError("truncated SNMP response")
    tag, n = buf[i], buf[i + 1]
    i += 2
    if n & 0x80:
        k = n & 0x7F
        n = int.from_bytes(buf[i : i + k], "big")
        i += k
    if i + n > len(buf):
        raise SnmpError("truncated SNMP response")
    return tag, buf[i : i + n], i + n


def build_get(oid: str, community: str = "public", request_id: int = 1) -> bytes:
    """Encode an SNMPv1 GetRequest for one OID."""
    varbind = _tlv(0x30, _tlv(0x30, _oid(oid) + b"\x05\x00"))
    pdu = _tlv(0xA0, _integer(request_id) + _integer(0) + _integer(0) + varbind)
    return _tlv(0x30, _integer(0) + _tlv(0x04, community.encode()) + pdu)


def parse_get_response(data: bytes) -> bytes:
    """Return the value of the single varbind in a GetResponse.

    Raises
    ------
    SnmpError
        On a malformed message, an SNMP error status, or a missing value.
    """
    _, message, _ = _read(data, 0)
    i = 0
    _, _, i = _read(message, i)  # version
    _, _, i = _read(message, i)  # community
    tag, pdu, _ = _read(message, i)
    if tag != 0xA2:
        raise SnmpError(f"not a GetResponse (PDU tag {tag:#04x})")
    j = 0
    _, _, j = _read(pdu, j)  # request id
    _, error_status, j = _read(pdu, j)
    _, _, j = _read(pdu, j)  # error index
    if int.from_bytes(error_status, "big"):
        raise SnmpError(f"SNMP error status {int.from_bytes(error_status, 'big')}")
    _, varbinds, _ = _read(pdu, j)
    _, varbind, _ = _read(varbinds, 0)
    _, _, k = _read(varbind, 0)  # oid
    value_tag, value, _ = _read(varbind, k)
    if value_tag in (0x80, 0x81, 0x82):  # noSuchObject / noSuchInstance / endOfMibView
        raise SnmpError("printer has no status object at this OID")
    return value


def snmp_get(
    host: str, oid: str, community: str = "public", timeout: float = 2.0, port: int = 161
) -> bytes:
    """Fetch one OID's value (raw bytes) with SNMPv1 over UDP."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.sendto(build_get(oid, community), (host, port))
            data, _ = sock.recvfrom(65535)
        except OSError as e:
            raise SnmpError(f"no SNMP answer from {host}: {e}") from e
    return parse_get_response(data)


def read_status(
    host: str, community: str = "public", timeout: float = 2.0, port: int = 161
) -> PrinterStatus:
    """Read and decode the status block of a network printer.

    Raises
    ------
    SnmpError
        If the printer does not answer or has no status object.
    StatusError
        If the value is not a status block.
    """
    return parse_status(snmp_get(host, STATUS_OID, community, timeout, port))
