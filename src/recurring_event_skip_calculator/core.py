"""Compute how many instances of a recurring event were missed.

The model is deliberately simple. A recurrence is one of three shapes:

  * DAILY  — every N days from a start date.
  * WEEKLY — every N weeks on a fixed set of weekday indexes (0 = Monday).
  * MONTHLY — every N months, on the same day-of-month as the start.

A "missed period" is a half-open range [miss_start, miss_end). Given the
rule and that range, :func:`calculate_skipped` returns the number of
instances that would have occurred inside the range.

Why this exists
---------------
When a service goes down or a user is inactive for a stretch, we need to
know how many scheduled occurrences were lost — for billing, for
notifications, or for catch-up scheduling. Doing this by counting every
day between two dates is slow for long ranges and fragile around time
zones, so this library works in calendar arithmetic only (via
:mod:`datetime`) and derives counts with closed-form or loop math rather
than enumerating every candidate day.

The trade-off
-------------
We ignore time-of-day entirely. Two events on the same calendar date are
the same instance regardless of hour. This makes the library unsuitable
for intra-day recurrences but removes a class of off-by-one bugs that
come from mixing wall-clock and UTC.

Edge case: MONTHLY rules with a start day of 29, 30, or 31 will silently
use the last day of shorter months (28 or 29). An instance is considered
"skipped" only if its (possibly clamped) date falls strictly inside the
missed range. If the clamped date lands on ``miss_end``, it is not
counted, because the range is half-open on the right.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


class Frequency(str, Enum):
    """Supported recurrence shapes.

    Inherits ``str`` so that serialized rules (JSON, YAML) round-trip as
    plain strings without a custom encoder.
    """

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass(frozen=True)
class RecurrenceRule:
    """A recurrence specification.

    Attributes:
        frequency: How the event repeats.
        start_date: The first occurrence. Calendar date only.
        interval: Skip ``interval - 1`` periods between occurrences. Must be
            at least 1. ``interval=1`` means every period.
        weekdays: For WEEKLY rules, the zero-based weekday indexes to fire on
            (0 = Monday … 6 = Sunday). Ignored for DAILY and MONTHLY. Must be
            non-empty when frequency is WEEKLY.
    """

    frequency: Frequency
    start_date: date
    interval: int = 1
    weekdays: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.interval < 1:
            raise ValueError("interval must be >= 1")
        if self.frequency is Frequency.WEEKLY and not self.weekdays:
            raise ValueError("weekly rules require at least one weekday")
        for wd in self.weekdays:
            if not 0 <= wd <= 6:
                raise ValueError(f"weekday {wd} is out of range 0-6")
        if self.frequency is Frequency.MONTHLY:
            if not 1 <= self.start_date.day <= 31:
                raise ValueError("start_date.day is out of range")


@dataclass(frozen=True)
class SkipResult:
    """Outcome of a skip calculation.

    Attributes:
        count: Number of instances in ``[miss_start, miss_end)``.
        first_skipped: The first instance date in the range, or ``None`` if
            the range contains zero instances.
        last_skipped: The last instance date in the range, or ``None``.
    """

    count: int
    first_skipped: date | None
    last_skipped: date | None


def _validate_range(miss_start: date, miss_end: date) -> None:
    if miss_end < miss_start:
        raise ValueError("miss_end must not precede miss_start")


def _monthly_clamped(year: int, month: int, target_day: int) -> date:
    """Return ``date(year, month, target_day)`` clamped to month length.

    ``target_day`` is the day-of-month from the rule's start. For months
    shorter than ``target_day`` we return the last day of that month. This
    matches the common "last-day" convention used by calendar apps.
    """
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(target_day, last))


def _advance_months(d: date, months: int) -> date:
    """Add ``months`` to ``d``, clamping the day to the target month length."""
    idx = d.year * 12 + (d.month - 1) + months
    year, month0 = divmod(idx, 12)
    return _monthly_clamped(year, month0 + 1, d.day)


def _daily_count(rule: RecurrenceRule, miss_start: date, miss_end: date) -> int:
    """Count occurrences strictly inside ``[miss_start, miss_end)``."""
    step = timedelta(days=rule.interval)

    delta_days = (miss_start - rule.start_date).days
    if delta_days <= 0:
        first = rule.start_date
    else:
        n = (delta_days + rule.interval - 1) // rule.interval
        first = rule.start_date + n * step
        if first < miss_start:
            first += step

    count = 0
    current = first
    while current < miss_end:
        count += 1
        current += step
    return count


def _weekly_count(rule: RecurrenceRule, miss_start: date, miss_end: date) -> int:
    """Count occurrences strictly inside ``[miss_start, miss_end)``.

    The anchor is ``start_date``. Within each ``interval``-week block we fire
    on every weekday in ``rule.weekdays``. We walk block by block so the cost
    is proportional to the number of blocks, not to the number of days.
    """
    step_weeks = rule.interval
    target_wds = sorted(set(rule.weekdays))
    week_delta = timedelta(weeks=step_weeks)

    def block_first(block_idx: int) -> date:
        return rule.start_date + block_idx * week_delta

    # Fast-forward to the first block whose end could overlap miss_start.
    span_days = (miss_start - rule.start_date).days
    if span_days <= 0:
        block_idx = 0
    else:
        # Each block spans `step_weeks` weeks; jump near the target.
        block_idx = max(0, span_days // (7 * step_weeks) - 1)

    count = 0
    first_skipped = None
    last_skipped = None
    block_start = block_first(block_idx)

    # Walk forward until we pass miss_end.
    while block_start < miss_end:
        for wd in target_wds:
            # Weekday of block_start gives the offset to the target weekday
            # within the same ISO week (Monday=0).
            offset = (wd - block_start.weekday()) % 7
            candidate = block_start + timedelta(days=offset)
            if miss_start <= candidate < miss_end:
                count += 1
                if first_skipped is None:
                    first_skipped = candidate
                last_skipped = candidate
        block_idx += 1
        block_start = block_first(block_idx)

    return count, first_skipped, last_skipped


def _monthly_count(rule: RecurrenceRule, miss_start: date, miss_end: date) -> int:
    """Count occurrences strictly inside ``[miss_start, miss_end)``."""
    target_day = rule.start_date.day

    def occurrence_at(block_idx: int) -> date:
        return _advance_months(rule.start_date, block_idx * rule.interval)

    span_days = (miss_start - rule.start_date).days
    if span_days <= 0:
        block_idx = 0
    else:
        # Estimate how many months the start is ahead of us.
        approx_blocks = span_days // (28 * rule.interval)
        block_idx = max(0, approx_blocks - 1)

    count = 0
    first_skipped = None
    last_skipped = None
    current = occurrence_at(block_idx)

    while current < miss_start:
        block_idx += 1
        current = occurrence_at(block_idx)

    while current < miss_end:
        count += 1
        if first_skipped is None:
            first_skipped = current
        last_skipped = current
        block_idx += 1
        current = occurrence_at(block_idx)

    return count, first_skipped, last_skipped


def calculate_skipped(
    rule: RecurrenceRule, miss_start: date, miss_end: date
) -> SkipResult:
    """Return how many instances of ``rule`` fall in ``[miss_start, miss_end)``.

    The range is half-open: an instance on ``miss_end`` is **not** counted.
    Instances before ``miss_start`` are ignored. An instance on the start date
    is counted only if it falls inside the range.

    Raises:
        ValueError: If ``miss_end`` precedes ``miss_start``.
    """
    _validate_range(miss_start, miss_end)

    if rule.frequency is Frequency.DAILY:
        count = _daily_count(rule, miss_start, miss_end)
        return _with_endpoints(count, rule, miss_start, miss_end, _daily_next)
    if rule.frequency is Frequency.WEEKLY:
        count, first, last = _weekly_count(rule, miss_start, miss_end)
        return SkipResult(count=count, first_skipped=first, last_skipped=last)
    # MONTHLY
    count, first, last = _monthly_count(rule, miss_start, miss_end)
    return SkipResult(count=count, first_skipped=first, last_skipped=last)


def _daily_next(rule: RecurrenceRule, d: date) -> date | None:
    """Return the first daily occurrence on or after ``d``, or None if none."""
    step = timedelta(days=rule.interval)
    if d <= rule.start_date:
        return rule.start_date
    delta = (d - rule.start_date).days
    rem = delta % rule.interval
    if rem == 0:
        return d
    return rule.start_date + timedelta(
        days=delta + (rule.interval - rem)
    )


def _with_endpoints(
    count: int,
    rule: RecurrenceRule,
    miss_start: date,
    miss_end: date,
    next_fn,
) -> SkipResult:
    """Build a SkipResult, deriving first/last only when count > 0.

    For DAILY we already have the count; we derive endpoints lazily so we
    don't do an extra pass when count is zero.
    """
    if count == 0:
        return SkipResult(count=0, first_skipped=None, last_skipped=None)
    first = next_fn(rule, miss_start)
    assert first is not None and first < miss_end  # invariant: count > 0
    last = first + timedelta(days=rule.interval * (count - 1))
    return SkipResult(count=count, first_skipped=first, last_skipped=last)
