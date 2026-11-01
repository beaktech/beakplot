"""Aggregate plain detection records without assuming a station or species."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, time, timedelta

import numpy as np


@dataclass(frozen=True)
class Detection:
    date: date
    time: time
    scientific_name: str
    detection_id: str | None = None
    monitor_id: str = ""
    review_status: str = ""
    common_name: str = ""
    confidence: float | None = None


@dataclass
class Counts:
    """Aligned with the requested dates; None means no retained records."""

    daily: list[int | None]
    quarter_hours: list[list[int] | None]
    coverage: list[int | None]


def validate_dates(dates):
    """The grid and rolling average require consecutive, ascending dates."""
    if not len(dates):
        raise ValueError("Provide at least one date")
    if any(b != a + timedelta(days=1) for a, b in zip(dates, dates[1:])):
        raise ValueError("Dates must be consecutive and in ascending order")


def aggregate(records, dates, species, *, excluded_ids=()):
    """Count one species over dates, using all retained species for coverage.

    IDs are de-duplicated within each monitor. Missing IDs are independent
    records. A false-positive review on any copy excludes that identity.
    Optional manual exclusions are (monitor_id, detection_id) pairs.
    Pass one station's records for a station chart; combining is explicit.
    Coverage is evidence of records, not proof of continuous recording.
    """
    validate_dates(dates)
    records = list(records)
    excluded = set(excluded_ids)
    excluded.update((r.monitor_id, r.detection_id) for r in records
                    if r.detection_id is not None and r.review_status == "false_positive")
    coverage, counts, bins = Counter(), Counter(), Counter()
    seen = set()
    wanted = set(dates)
    for row in records:
        identity = (row.monitor_id, row.detection_id)
        if row.review_status == "false_positive" or identity in excluded:
            continue
        if row.detection_id is not None:
            if identity in seen:
                continue
            seen.add(identity)
        if row.date not in wanted:
            continue
        coverage[row.date] += 1
        if row.scientific_name == species:
            counts[row.date] += 1
            bins[row.date, row.time.hour * 4 + row.time.minute // 15] += 1
    return Counts(
        daily=[counts[d] if coverage[d] else None for d in dates],
        quarter_hours=[[bins[d, slot] for slot in range(96)] if coverage[d] else None
                       for d in dates],
        coverage=[coverage[d] or None for d in dates],
    )


def trailing_mean(values, dates):
    """Seven-day mean, only where all seven consecutive days have records."""
    validate_dates(dates)
    values = np.asarray(values, dtype=float)
    if values.shape != (len(dates),):
        raise ValueError("Provide one daily count per date")
    return np.array([np.mean(values[i-6:i+1]) if i >= 6 else np.nan
                     for i in range(len(values))])
