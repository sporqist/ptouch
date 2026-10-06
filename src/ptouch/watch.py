# SPDX-FileCopyrightText: 2026 Marius Alwan Meyer
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Watch a network printer while a job runs.

Network P-touch printers cannot be stopped remotely (an ``ESC @`` sent
on a second connection mid-job was ignored by a PT-E550W), so the only
remedy for a job that keeps feeding tape is a person at the power
button. ``watch_job`` polls the printer over SNMP and calls
``on_overrun`` as soon as a job runs longer than expected, so that
person is alerted within seconds.

Signals, both read over SNMP v1:

- ``hrPrinterStatus`` (HOST-RESOURCES-MIB, 1.3.6.1.2.1.25.3.5.1.1.1):
  3 = idle, 4 = printing. Standard, so it works across vendors.
- The Brother status block (see :mod:`ptouch.snmp`) for error bits.

Verified on a PT-E550W (firmware 1.31): a single label read 3, then 4
from 0.55 s to 5.8 s, then 3 again at 6.3 s.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from .snmp import SnmpError, read_status, snmp_get
from .status import PrinterStatus, StatusError

HR_PRINTER_STATUS = "1.3.6.1.2.1.25.3.5.1.1.1"
IDLE, PRINTING = 3, 4


class Outcome(Enum):
    """How a watched job ended."""

    COMPLETED = "completed"  # printed, back to idle within the time budget
    OVERRUN = "overrun"  # still printing past the budget (on_overrun was called)
    ERROR = "error"  # the printer reported an error
    NOT_STARTED = "not started"  # never seen printing
    UNREACHABLE = "unreachable"  # no SNMP answers


@dataclass
class WatchResult:
    """What the watchdog saw."""

    outcome: Outcome
    seconds: float
    errors: list[str] = field(default_factory=list)
    samples: list[tuple[float, int | None]] = field(default_factory=list)


def estimate_seconds(pages: int) -> float:
    """Estimate the print time for a job of ``pages`` labels.

    Calibrated on a PT-E550W with ~16-19 mm labels on 24 mm tape (1 label
    6.4 s, 2-label strip 10.6 s, 3-label strip 13.2 s), rounded up.
    """
    return 3.0 + 4.0 * pages


def printer_state(host: str, timeout: float = 1.0) -> int:
    """Read ``hrPrinterStatus`` of a network printer (3 idle, 4 printing)."""
    value = snmp_get(host, HR_PRINTER_STATUS, timeout=timeout)
    return int.from_bytes(value, "big")


def watch_job(  # noqa: C901 - one polling loop with several exits
    host: str,
    expected_seconds: float,
    *,
    slack_seconds: float = 8.0,
    hard_limit_factor: float = 3.0,
    poll_seconds: float = 0.5,
    start_seconds: float = 5.0,
    on_overrun: Callable[[float], None] | None = None,
    state_reader: Callable[[], int] | None = None,
    status_reader: Callable[[], PrinterStatus] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> WatchResult:
    """Poll the printer from just after sending a job until it is idle again.

    Parameters
    ----------
    host : str
        Printer address.
    expected_seconds : float
        How long the job should take (see :func:`estimate_seconds`).
    slack_seconds : float
        Allowance on top of ``expected_seconds`` before ``on_overrun``.
    hard_limit_factor : float
        Stop watching (outcome OVERRUN) after this many times the budget.
    poll_seconds : float
        Polling interval.
    start_seconds : float
        Give up (NOT_STARTED) if the printer never reports printing in this time.
    on_overrun : callable, optional
        Called once with the elapsed seconds when the budget is exceeded
        while the printer still prints. Alert a person here.
    state_reader, status_reader, clock, sleep : callable, optional
        Injection points for tests; default to SNMP and real time.

    Returns
    -------
    WatchResult
        The outcome, elapsed time, error names and the state samples.
    """
    read_state = state_reader or (lambda: printer_state(host))
    read_block = status_reader or (lambda: read_status(host, timeout=1.0))
    budget = expected_seconds + slack_seconds
    start = clock()
    seen_printing = False
    alerted = False
    failures = 0
    result = WatchResult(Outcome.NOT_STARTED, 0.0)

    while True:
        elapsed = clock() - start
        result.seconds = elapsed
        try:
            state: int | None = read_state()
            failures = 0
        except SnmpError:
            state = None
            failures += 1
        result.samples.append((round(elapsed, 2), state))

        if failures >= 6:
            result.outcome = Outcome.UNREACHABLE
            return result
        try:
            block = read_block()
            if block.has_error:
                result.outcome, result.errors = Outcome.ERROR, block.errors or ["error status"]
                return result
        except (SnmpError, StatusError):
            pass

        if state == PRINTING:
            seen_printing = True
        elif state == IDLE and seen_printing:
            result.outcome = Outcome.COMPLETED if not alerted else Outcome.OVERRUN
            return result
        elif state == IDLE and elapsed > start_seconds:
            result.outcome = Outcome.NOT_STARTED
            return result

        if elapsed > budget and not alerted and state != IDLE:
            alerted = True
            if on_overrun:
                on_overrun(elapsed)
        if elapsed > budget * hard_limit_factor:
            result.outcome = Outcome.OVERRUN
            return result
        sleep(poll_seconds)
