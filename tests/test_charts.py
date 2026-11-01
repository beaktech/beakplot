from datetime import date, timedelta
from io import BytesIO
import warnings

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pytest

from dayclock import daily_counts, day_clock, sun_times
from dayclock.heatmap import clock_name


def test_sunrise_and_sunset_at_greenwich_summer_solstice():
    # US Naval Observatory: 04:43 / 21:21, UTC+1 at 51.4779 N, 0 E.
    # https://aa.usno.navy.mil/api/rstt/oneday?date=2026-06-21&coords=51.4779,0&tz=1
    # Fixed external reference; tests make no network calls. Allow two minutes
    # for the simpler fractional-year approximation and rounded reference.
    rise, sunset = sun_times(date(2026, 6, 21), 51.4779, 0, "Europe/London")
    assert rise == pytest.approx(4 + 43 / 60, abs=2 / 60)
    assert sunset == pytest.approx(21 + 21 / 60, abs=2 / 60)


@pytest.mark.parametrize("day,offset", [(date(2026, 6, 21), 1), (date(2026, 12, 21), 0)])
def test_sun_times_use_date_specific_time_zone_offset(day, offset):
    utc = np.array(sun_times(day, 51.4779, 0, "UTC"))
    local = np.array(sun_times(day, 51.4779, 0, "Europe/London"))
    np.testing.assert_allclose(local - utc, offset, atol=1 / 3600)
    other = np.array(sun_times(day, 51.4779, 0, "Asia/Kolkata"))
    np.testing.assert_allclose((other - utc) % 24, 5.5, atol=1 / 3600)


def test_clock_label_across_clock_change():
    assert clock_name([date(2026, 10, 24), date(2026, 10, 25)], "Europe/London") == "local clock time"


def test_polar_day_has_a_clear_error():
    with pytest.raises(ValueError, match="No sunrise/sunset"):
        sun_times(date(2026, 6, 21), 80, 0, "UTC")


def test_heatmap_unknown_hatching_zero_transparency_and_fixed_colour_scale():
    day = date(2025, 4, 1)
    dates = [day + timedelta(days=i) for i in range(3)]
    row = [0] * 96
    row[0] = row[48] = 5
    fig = day_clock([None, [0] * 96, row], dates, 50, 0, tz="UTC", vmax=20)
    ax = fig.axes[0]
    mesh = ax.collections[1]
    assert mesh.get_clim() == (1, 20)
    fig.canvas.draw()
    colours = mesh.get_facecolors().reshape(96, 3, 4)
    assert (colours[:, :2, 3] == 0).all()
    np.testing.assert_array_equal(colours[0, 2], colours[48, 2])
    assert colours[0, 2, 3] == 1
    hatched = [p for p in ax.patches if p.get_hatch()]
    assert len(hatched) == 1
    assert hatched[0].get_x() == mdates.date2num(day)


@pytest.mark.parametrize("rows", [[[0] * 96], [None]])
def test_empty_heatmap_does_not_warn_and_can_save_svg_and_png(rows):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        fig = day_clock(rows, [date(2025, 4, 1)], 50, 0, tz="UTC")
        for fmt in ("svg", "png"):
            stream = BytesIO()
            fig.savefig(stream, format=fmt)
            assert stream.tell() > 0


def test_single_station_unknown_shading_is_centred_on_its_daily_bar():
    dates = [date(2025, 4, 1) + timedelta(days=i) for i in range(3)]
    fig = daily_counts({"Synthetic station": [4, None, 0]}, dates,
                       annotate_last=["Synthetic station"])
    ax = fig.axes[0]
    shade = next(p for p in ax.patches if np.allclose(p.get_facecolor()[:3], [236/255, 238/255, 241/255]))
    assert shade.get_x() == mdates.date2num(dates[1]) - .5
    assert shade.get_width() == 1
    assert ax.patches[2].get_height() == 0
    assert any("automatic identifications" in t.get_text() for t in fig.texts)
    fig.savefig(BytesIO(), format="svg")


def test_zero_series_with_annotation_request_does_not_crash_or_change_global_style():
    before = plt.rcParams.copy()
    daily_counts({"Synthetic station": [0]}, [date(2025, 4, 1)],
                 annotate_last=["Synthetic station"])
    assert dict(plt.rcParams) == dict(before)


@pytest.mark.parametrize("rows,vmax", [([[0] * 95], None), ([[0] * 96], 0),
                                       ([[-1] * 96], None), ([[np.nan] * 96], None)])
def test_invalid_heatmap_counts(rows, vmax):
    with pytest.raises(ValueError):
        day_clock(rows, [date(2025, 4, 1)], 50, 0, vmax=vmax)


@pytest.mark.parametrize('vmax,label', [(1, '1+'), (2.5, '2.5+')])
def test_fixed_small_colour_limits_have_a_label_without_warnings(vmax, label):
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        fig = day_clock([[3] * 96], [date(2025, 4, 1)], 50, 0, tz='UTC', vmax=vmax)
        fig.savefig(BytesIO(), format='svg')
    assert fig.axes[1].get_xticklabels()[-1].get_text() == label


@pytest.mark.parametrize('length', [1, 3, 21])
def test_short_heatmap_daylight_labels_stay_inside_figure(length):
    dates = [date(2025, 4, 1) + timedelta(days=i) for i in range(length)]
    fig = day_clock([[0] * 96 for _ in dates], dates, 50, 0, tz='UTC')
    fig.canvas.draw()
    labels = [t for t in fig.axes[0].texts if t.get_text() in ('Sunrise', 'Sunset', 'Night')]
    assert len(labels) == 4
    assert all(t.get_window_extent().x1 <= fig.bbox.x1 for t in labels)
