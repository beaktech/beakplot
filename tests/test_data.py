from datetime import date, time, timedelta

import numpy as np
import pytest

from dayclock import Detection, aggregate, trailing_mean


START = date(2025, 3, 1)


def days(n):
    return [START + timedelta(days=i) for i in range(n)]


def record(day=START, species="Species alpha", identity=None, monitor="a", review=""):
    return Detection(day, time(6, 29), species, identity, monitor, review)


def test_unknown_days_and_recorded_zero_days():
    dates = days(3)
    result = aggregate([record(dates[1], "Species beta"), record(dates[2])],
                       dates, "Species alpha")
    assert result.daily == [None, 0, 1]
    assert result.coverage == [None, 1, 1]
    assert result.quarter_hours[0] is None
    assert result.quarter_hours[1] == [0] * 96
    assert sum(result.quarter_hours[2]) == 1
    assert result.quarter_hours[2][25] == 1


def test_average_needs_seven_consecutive_recorded_days_including_zero():
    values = [1, 2, 3, 4, 5, 6, 0, None, 2, 2, 2, 2, 2, 2, 2]
    result = trailing_mean(values, days(len(values)))
    assert np.isnan(result[:6]).all()
    assert result[6] == 3
    assert np.isnan(result[7:14]).all()
    assert result[14] == 2


def test_seven_rows_cannot_disguise_a_missing_calendar_day():
    dates = days(8)
    del dates[3]
    with pytest.raises(ValueError, match="consecutive"):
        trailing_mean([1] * 7, dates)


def test_false_positives_are_excluded_from_counts_bins_and_coverage():
    dates = days(2)
    result = aggregate([record(review="false_positive"),
                        record(dates[1], "Species beta"),
                        record(dates[1], review="false_positive")], dates, "Species alpha")
    assert result.daily == [None, 0]
    assert result.coverage == [None, 1]
    assert result.quarter_hours == [None, [0] * 96]


def test_detection_ids_are_de_duplicated_per_monitor():
    rows = [record(identity="1"), record(identity="1"),
            record(identity="1", monitor="b"), record(), record()]
    result = aggregate(rows, [START], "Species alpha")
    assert result.daily == [4]
    assert result.coverage == [4]
    assert result.quarter_hours[0][25] == 4


@pytest.mark.parametrize("reverse", [False, True])
def test_false_positive_review_wins_over_an_unreviewed_duplicate(reverse):
    rows = [record(identity="1"), record(identity="1", review="false_positive")]
    if reverse:
        rows.reverse()
    assert aggregate(rows, [START], "Species alpha").daily == [None]


def test_manual_exclusions_are_scoped_to_monitor():
    rows = [record(identity="1"), record(identity="1", monitor="b")]
    result = aggregate(rows, [START], "Species alpha", excluded_ids=[("a", "1")])
    assert result.daily == [1]
    assert result.coverage == [1]


def test_records_outside_requested_dates_do_not_establish_coverage():
    assert aggregate([record(START - timedelta(days=1))], [START], "Species alpha").daily == [None]


@pytest.mark.parametrize("dates", [[], [START, START], [START + timedelta(days=1), START]])
def test_invalid_date_grid(dates):
    with pytest.raises(ValueError):
        aggregate([], dates, "Species alpha")
