# recurring-event-skip-calculator

Given a recurring event rule and a missed period, computes how many instances were skipped.

## Usage

```python
from datetime import date
from recurring_event_skip_calculator import RecurrenceRule, calculate_skipped, SkipResult
from recurring_event_skip_calculator.core import Frequency

rule = RecurrenceRule(
    frequency=Frequency.WEEKLY,
    start_date=date(2024, 1, 1),
    interval=2,
    weekdays=(0,),  # Monday
)
result: SkipResult = calculate_skipped(rule, date(2024, 1, 10), date(2024, 2, 1))
print(result.count)            # 2
print(result.first_skipped)    # 2024-01-15
print(result.last_skipped)     # 2024-01-29
```

## Exported names

- `RecurrenceRule` — frozen dataclass with fields `frequency`, `start_date`, `interval`, `weekdays`.
- `SkipResult` — frozen dataclass with fields `count`, `first_skipped`, `last_skipped`.
- `calculate_skipped(rule, miss_start, miss_end) -> SkipResult`
- `Frequency` (from `recurring_event_skip_calculator.core`) — enum: `DAILY`, `WEEKLY`, `MONTHLY`.

## Why this exists

When a service goes down or a user is inactive for a stretch, you need to know how many scheduled occurrences were lost — for billing, for notifications, or for catch-up scheduling. Counting every day between two dates is slow for long ranges and fragile around time zones, so this library works in calendar arithmetic only (via `datetime`) and derives counts with closed-form or loop math over blocks, not over individual days.

The trade-off: we ignore time-of-day entirely. Two events on the same calendar date are the same instance regardless of hour. This makes the library unsuitable for intra-day recurrences but removes a class of off-by-one bugs that come from mixing wall-clock and UTC.

## The awkward edge

The missed range is **half-open**: `[miss_start, miss_end)`. An instance landing exactly on `miss_end` is not counted. For MONTHLY rules with a start day of 29, 30, or 31, shorter months clamp to the last day of that month (so January 31 rolls to February 28 or 29). An instance is counted only if its clamped date falls strictly inside the range.

## Running the tests

```
PYTHONPATH=src python -m unittest discover -s tests
```

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

