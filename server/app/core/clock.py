"""Injectable time source so services and tests share one notion of "today".

The default clock is the real system date: simulations describe a transfer
happening now, and data staleness is surfaced (as-of dates, stale-value
caveats) rather than hidden by pinning time to the dataset's cut-off.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, cast

from fastapi import Request


class Clock(Protocol):
    def today(self) -> date: ...


def get_clock(request: Request) -> Clock:
    return cast(Clock, request.app.state.clock)


class SystemClock:
    def today(self) -> date:
        return date.today()


@dataclass(frozen=True)
class FixedClock:
    fixed: date

    def today(self) -> date:
        return self.fixed
