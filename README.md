# flight-duty-period

A small, dependency-free Python library that checks a single flight crew duty period against EASA-style flight time limitation (FTL) rules. It reports whether the period is compliant, which limit is the binding constraint, and how much headroom remains.

## Usage

```python
from datetime import datetime, timedelta
from flight_duty_period import DutyPeriod, calculate_duty, calculate_rest

start = datetime(2024, 6, 1, 6, 0)   # report time
end   = datetime(2024, 6, 1, 18, 0) # release time
flight = timedelta(hours=7, minutes=30)

period = DutyPeriod(start, end, flight, sectors=2)

duty = calculate_duty(period)
print(duty.compliant, duty.remaining, duty.limiting_factor)

rest = calculate_rest(period, timedelta(hours=20))
print(rest.compliant, rest.required_rest)
```

## Why this exists

Crew scheduling systems need to answer one question thousands of times per day: is this pairing legal? That question has many moving parts — local time, acclimatisation, in-flight rest facilities, commander's discretion — and a full FTL engine is a large, configuration-heavy system. This library deliberately covers only the **single-period daily limits** so a caller can do a fast pre-check before handing a candidate roster to the heavier downstream system. The trade-off is speed and simplicity against regulatory completeness; the caller is responsible for anything beyond one duty period at a time.

## Interpretation decisions

- Rules follow EASA ORO.FTL.105 / ORO.FTL.205 daily-limit tables. Augmented crew limits assume an onboard rest facility; the caller must set `augmented=True` only when that is genuinely the case.
- Datetimes must be **naive** (wall-clock, no timezone). FTL rules operate on local report/release times and timezone arithmetic is the caller's job.
- Post-duty minimum rest is `max(10h, duty + 2h)`. Ten hours is the absolute regulatory floor and is never reduced below.
- Taxi time is excluded from flight time but included in duty time, matching the standard EASA convention.

## Edge case you will hit

A duty that ends at exactly the limit duration is **non-compliant** — the limits are ceilings, not targets. If you need a compliant result, schedule the release one minute earlier than the limit. The library returns `remaining=timedelta(0)` and `compliant=False` in that case; there is no "just over the line is fine" tolerance.

## API

- `DutyPeriod(start, end, flight_time, augmented=False, sectors=1)` — immutable, validates in `__post_init__`.
- `calculate_duty(dp) -> DutyResult(max_duty, actual_duty, remaining, compliant, limiting_factor)` — checks flight time and duty duration against the sector/augmentation tables.
- `calculate_rest(dp, provided_rest) -> RestResult(required_rest, provided_rest, compliant)` — checks the rest scheduled after this duty meets the minimum.
