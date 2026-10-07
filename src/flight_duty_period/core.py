from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Tuple


__all__ = [
    "DutyPeriod",
    "DutyResult",
    "RestResult",
    "calculate_duty",
    "calculate_rest",
]


@dataclass(frozen=True)
class DutyPeriod:
    """Concrete description of one flight crew duty period.

    A duty period starts when a crew member reports for duty (e.g. at the
    airport for a briefing) and ends when they are released from duty after
    the last leg. The *flight time* is the airborne portion only; taxi time
    on the ground is excluded from flight time but included in duty time,
    which is the standard EASA/NCAA convention.
    """

    start: datetime
    end: datetime
    flight_time: timedelta
    augmented: bool = False
    sectors: int = 1

    def __post_init__(self) -> None:
        # ``object.__setattr__`` because the dataclass is frozen.
        if self.start.tzinfo is not None or self.end.tzinfo is not None:
            raise ValueError("DutyPeriod datetimes must be naive (wall clock); use UTC if needed.")
        if self.end <= self.start:
            raise ValueError("DutyPeriod end must be strictly after start.")
        if self.flight_time < timedelta(0):
            raise ValueError("flight_time cannot be negative.")
        duty = self.end - self.start
        if self.flight_time > duty:
            raise ValueError("flight_time cannot exceed total duty duration.")
        if self.sectors < 1:
            raise ValueError("sectors must be at least 1.")

    @property
    def duty_duration(self) -> timedelta:
        return self.end - self.start


@dataclass(frozen=True)
class DutyResult:
    max_duty: timedelta
    actual_duty: timedelta
    remaining: timedelta
    compliant: bool
    limiting_factor: str


@dataclass(frozen=True)
class RestResult:
    required_rest: timedelta
    provided_rest: timedelta
    compliant: bool


def _max_flight_time(dp: DutyPeriod) -> timedelta:
    """EASA OML.A.FTM.105 Table 1 — maximum daily flight time.

    The augmented crew column applies when ``dp.augmented`` is True, which in
    a real operation also requires a rest facility on board; this library
    trusts the caller to set ``augmented`` only when that is genuinely the
    case.
    """
    if dp.sectors <= 2:
        return timedelta(hours=13 if dp.augmented else 10)
    if dp.sectors <= 4:
        return timedelta(hours=12.5 if dp.augmented else 9)
    return timedelta(hours=11 if dp.augmented else 8)


def _max_duty_duration(dp: DutyPeriod) -> timedelta:
    """EASA ORO.FTL.105 / ORO.FTL.205 Table 2 — maximum flight duty period.

    Times given in the source as 13h00, 14h00 etc. are translated here to
    ``timedelta``. The same table is used for local base departure in
    daytime; we deliberately do **not** model the local-night reduction because
    doing so correctly requires knowing local time and the base's night
    window, which is outside the scope of this library.
    """
    if dp.sectors <= 1:
        return timedelta(hours=14 if dp.augmented else 13)
    if dp.sectors <= 2:
        return timedelta(hours=13.5 if dp.augmented else 13)
    if dp.sectors <= 3:
        return timedelta(hours=13 if dp.augmented else 12.5)
    if dp.sectors <= 4:
        return timedelta(hours=12.5 if dp.augmented else 12)
    if dp.sectors <= 5:
        return timedelta(hours=12 if dp.augmented else 11.5)
    if dp.sectors <= 6:
        return timedelta(hours=11.5 if dp.augmented else 11)
    return timedelta(hours=11 if dp.augmented else 10.5)


def calculate_duty(dp: DutyPeriod) -> DutyResult:
    """Evaluate a single DutyPeriod against EASA FTL daily limits.

    The rule that binds first — the one that actually limits the operation —
    is reported as ``limiting_factor``. ``remaining`` is always non-negative
    and expresses the headroom against whichever limit was tighter.
    """
    max_flight = _max_flight_time(dp)
    max_duty = _max_duty_duration(dp)

    if dp.flight_time >= max_flight:
        return DutyResult(
            max_duty=max_duty,
            actual_duty=dp.duty_duration,
            remaining=timedelta(0),
            compliant=False,
            limiting_factor="flight_time",
        )
    if dp.duty_duration >= max_duty:
        return DutyResult(
            max_duty=max_duty,
            actual_duty=dp.duty_duration,
            remaining=timedelta(0),
            compliant=False,
            limiting_factor="duty_duration",
        )
    flight_remaining = max_flight - dp.flight_time
    duty_remaining = max_duty - dp.duty_duration
    return DutyResult(
        max_duty=max_duty,
        actual_duty=dp.duty_duration,
        remaining=min(flight_remaining, duty_remaining),
        compliant=True,
        limiting_factor="flight_time" if flight_remaining <= duty_remaining else "duty_duration",
    )


def _rest_for_duty(dp: DutyPeriod) -> timedelta:
    """EASA ORO.FTL.105 Table 2 — minimum post-flight duty rest.

    Two regimes: under 10h duty gets 10h rest (the source floor), at or above
    10h duty gets duty + 2h, never less than the 10h floor. Ten hours is the
    absolute regulatory minimum irrespective of how short the duty was.
    """
    if dp.duty_duration < timedelta(hours=10):
        return timedelta(hours=10)
    return dp.duty_duration + timedelta(hours=2)


def calculate_rest(dp: DutyPeriod, provided_rest: timedelta) -> RestResult:
    """Check that rest before the next duty meets the minimum for this one.

    ``provided_rest`` is the duration of the uninterrupted rest period that
    the operator scheduled immediately after this duty. It must be a real,
    positive duration; anything else is a programming error and is rejected
    rather than silently coerced.
    """
    if provided_rest <= timedelta(0):
        raise ValueError("provided_rest must be a positive duration.")
    required = _rest_for_duty(dp)
    return RestResult(
        required_rest=required,
        provided_rest=provided_rest,
        compliant=provided_rest >= required,
    )
