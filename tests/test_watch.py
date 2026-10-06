# SPDX-FileCopyrightText: 2026 Marius Alwan Meyer
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for the print watchdog (simulated printer, simulated time)."""

from collections.abc import Callable

from ptouch.snmp import SnmpError
from ptouch.status import PrinterStatus, parse_status
from ptouch.watch import IDLE, PRINTING, Outcome, WatchResult, estimate_seconds, watch_job

READY = bytes.fromhex(
    "80 20 42 30 66 30 04 00 00 00 18 01 00 00 00 40 "  # header, 24 mm laminated
    "00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00"  # black on white, no errors
)


class FakePrinter:
    """Plays back a printer state timeline against a fake clock."""

    def __init__(
        self, timeline: list[tuple[float, int | None]], error_at: float | None = None
    ) -> None:
        self.timeline = timeline
        self.error_at = error_at
        self.now = 0.0

    def clock(self) -> float:
        """Fake monotonic clock."""
        return self.now

    def sleep(self, seconds: float) -> None:
        """Advance the fake clock instead of sleeping."""
        self.now += seconds

    def state(self) -> int:
        """HrPrinterStatus at the current fake time (None = no answer)."""
        current: int | None = IDLE
        for t, s in self.timeline:
            if self.now >= t:
                current = s
        if current is None:
            raise SnmpError("timeout")
        return current

    def status(self) -> PrinterStatus:
        """Status block, with a cutter jam from ``error_at`` on."""
        block = bytearray(READY)
        if self.error_at is not None and self.now >= self.error_at:
            block[8] = 0x04  # cutter jam
        return parse_status(bytes(block))

    def watch(self, expected: float, slack: float = 8.0) -> tuple[WatchResult, list[float]]:
        """Run the watchdog against this fake printer; return result and alerts."""
        alerts: list[float] = []
        on: Callable[[float], None] = alerts.append
        result = watch_job(
            "printer",
            expected,
            slack_seconds=slack,
            state_reader=self.state,
            status_reader=self.status,
            clock=self.clock,
            sleep=self.sleep,
            on_overrun=on,
        )
        return result, alerts


def test_normal_job_completes() -> None:
    """Printing for 6 s, then idle: completed, no alert."""
    p = FakePrinter([(0, PRINTING), (6.0, IDLE)])
    result, alerts = p.watch(estimate_seconds(1))
    assert result.outcome is Outcome.COMPLETED
    assert alerts == []


def test_runaway_job_alerts_early() -> None:
    """A job that keeps printing triggers the alert right after the budget."""
    p = FakePrinter([(0, PRINTING)])  # never stops
    result, alerts = p.watch(7.0, slack=8.0)
    assert result.outcome is Outcome.OVERRUN
    assert len(alerts) == 1 and 15.0 < alerts[0] <= 16.0


def test_late_finish_after_alert_is_overrun() -> None:
    """An alert was raised, even if the job finishes later."""
    p = FakePrinter([(0, PRINTING), (20.0, IDLE)])
    result, alerts = p.watch(7.0, slack=8.0)
    assert result.outcome is Outcome.OVERRUN
    assert len(alerts) == 1


def test_error_bits_end_the_watch() -> None:
    """A status-block error is reported with its name."""
    p = FakePrinter([(0, PRINTING)], error_at=2.0)
    result, _ = p.watch(7.0)
    assert result.outcome is Outcome.ERROR
    assert result.errors == ["cutter jam"]


def test_never_starts() -> None:
    """Idle the whole time: not started."""
    p = FakePrinter([(0, IDLE)])
    result, alerts = p.watch(7.0)
    assert result.outcome is Outcome.NOT_STARTED
    assert alerts == []


def test_unreachable() -> None:
    """Repeated SNMP failures end the watch as unreachable."""
    p = FakePrinter([(0, None)])
    result, _ = p.watch(7.0)
    assert result.outcome is Outcome.UNREACHABLE


def test_estimate_matches_measured_times() -> None:
    """The estimate stays above the times measured on a PT-E550W."""
    for pages, measured in [(1, 6.4), (2, 10.6), (3, 13.2)]:
        assert estimate_seconds(pages) >= measured
