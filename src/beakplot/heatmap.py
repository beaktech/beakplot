"""Beak Tech's daylight heatmap: detections by date and time of day.

Each column is one day and each square 15 minutes, drawn over that place's
daylight (between the day's real sunrise and sunset) and night, so readers can
see at a glance whether a pattern belongs to dawn, the day or dusk.

    from beakplot import day_clock
    fig = day_clock(rows, dates, lat, lon, title=..., subtitle=...)

`rows` holds one entry per date: 96 quarter-hour detection counts, or None for
a day with no recordings at all. Inside a recorded day a blank square means
nothing was detected, which assumes the recorder ran all day.

Rules the design keeps, so charts stay comparable across posts:
- A square with detections is solid: the same count is the same colour by day
  or by night. Squares with none are left clear to show the day or night behind.
- Days without recordings are hatched, never shown as zero.
- Sunrise and sunset come from the location and date, in local clock time.
- Pass the same `vmax` to charts that are meant to be compared.
"""
from calendar import isleap
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

from .data import validate_dates
from .style import DEFAULT_SUBTITLE, add_logo, styled

INK = '#33465e'
NIGHT = '#e3e9f1'
DAY = '#fefaf0'
SUN_LINE = '#c9a24a'
SUN_TEXT = '#8a6a22'
HATCH = '#aab6c4'
DETECTIONS = LinearSegmentedColormap.from_list(
    'beak-detections', ['#fcd9c3', '#f7a072', '#f15a29', '#a8320f', '#5e1a06'])


def sun_times(day, lat, lon, tz=None):
    """NOAA approximate sunrise/sunset in local clock hours.

    `tz` is an IANA name or tzinfo; None uses the system time zone.
    This fractional-year approximation can differ by several minutes from
    full solar ephemerides. Polar days/nights have no pair of sun crossings.
    """
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Latitude or longitude is out of range")
    tz = ZoneInfo(tz) if isinstance(tz, str) else tz
    g = 2 * np.pi / (366 if isleap(day.year) else 365) * (day.timetuple().tm_yday - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                       - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    phi = np.radians(lat)
    cosine = (np.cos(np.radians(90.833)) / (np.cos(phi) * np.cos(decl))
              - np.tan(phi) * np.tan(decl))
    if not -1 <= cosine <= 1:
        raise ValueError("No sunrise/sunset pair on this date at this latitude")
    half_day = np.degrees(np.arccos(cosine))
    noon = 720 - 4 * lon - eqtime  # minutes after midnight UTC
    times = []
    for minutes in (noon - 4 * half_day, noon + 4 * half_day):
        local = (datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
                 + timedelta(minutes=minutes)).astimezone(tz)
        times.append(local.hour + local.minute / 60 + local.second / 3600)
    return times


def clock_name(dates, tz=None):
    """Time zone abbreviation, or local clock time across a clock change."""
    tz = ZoneInfo(tz) if isinstance(tz, str) else tz
    names = {datetime(d.year, d.month, d.day, 12).replace(tzinfo=tz).astimezone(tz).tzname()
             for d in dates}
    return names.pop() if len(names) == 1 else 'local clock time'


def nice_limit(values):
    """A round upper limit for the colour scale, near the 99th percentile."""
    top = np.nanpercentile(values, 99) if np.isfinite(values).any() else 1
    step = 5 if top <= 20 else 10 if top <= 100 else 50
    return max(step, int(np.ceil(top / step) * step))


@styled
def day_clock(rows, dates, lat, lon, *, title="Detections by date and time",
              subtitle=DEFAULT_SUBTITLE, vmax=None, note=None, tz=None, logo=None):
    """Draw the chart and return the figure. `note` is ((date, hour), (date, hour), text)."""
    validate_dates(dates)
    if len(rows) != len(dates) or any(r is not None and len(r) != 96 for r in rows):
        raise ValueError("Provide 96 quarter-hour counts or None for each date")
    counts = np.array([[np.nan] * 96 if r is None else r for r in rows], dtype=float).T
    missing = np.array([r is None for r in rows])
    detected = np.where(counts > 0, counts, np.nan)
    if np.any(np.isinf(counts)) or np.any(counts < 0) or any(
            r is not None and not np.isfinite(r).all() for r in rows):
        raise ValueError("Recorded days must contain finite, non-negative counts")
    if vmax is not None and (not np.isfinite(vmax) or vmax < 1):
        raise ValueError("vmax must be finite and at least 1")
    vmax = nice_limit(detected) if vmax is None else vmax

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_axes([0.13, 0.11, 0.75, 0.6])
    x0 = mdates.date2num(dates[0])
    x1 = mdates.date2num(dates[-1] + timedelta(days=1))
    mids = np.array([mdates.date2num(d) + 0.5 for d in dates])
    rise, sets = np.array([sun_times(d, lat, lon, tz) for d in dates]).T

    # Night everywhere, then the day's daylight, both behind the detections.
    ax.add_patch(Rectangle((x0, 0), x1 - x0, 24, color=NIGHT, lw=0, zorder=0))
    ax.fill_between(np.r_[x0, mids, x1], np.r_[rise[0], rise, rise[-1]],
                    np.r_[sets[0], sets, sets[-1]], color=DAY, lw=0, zorder=1)

    mesh = ax.pcolormesh(np.arange(len(dates) + 1) + x0, np.linspace(0, 24, 97), detected,
                         cmap=DETECTIONS, vmin=1, vmax=vmax, shading='flat',
                         edgecolors=(1, 1, 1, 0.35), linewidth=0.15, zorder=2, rasterized=True)
    for i in np.flatnonzero(missing):
        ax.add_patch(Rectangle((x0 + i, 0), 1, 24, facecolor='white', edgecolor=HATCH,
                               hatch='////', lw=0, zorder=3))

    for series, label in ((sets, 'Sunset'), (rise, 'Sunrise')):
        ax.plot(mids, series, color=SUN_LINE, lw=1.1, zorder=4)
        ax.text(x1 + min(1.2, (x1 - x0) * .02), series[-1], label, ha='left', va='center', fontsize=10.5,
                color=SUN_TEXT, fontweight='bold', clip_on=False)
    for hour in (23, 1):
        ax.text(x0 + min(1.5, (x1 - x0) * .04), hour, 'Night', ha='left', va='center', fontsize=10.5, color='#6b7d91', zorder=5)

    ax.set_xlim(x0, x1)
    ax.set_ylim(0, 24)
    ax.set_yticks([0, 6, 12, 18, 24], ['Midnight', '6am', 'Noon', '6pm', 'Midnight'])
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%B'))
    ax.tick_params(length=0, pad=8, labelsize=11, colors=INK)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_ylabel(f'Time of day ({clock_name(dates, tz)})', fontsize=11, color=INK, labelpad=10)

    if note:
        (px, py), (tx, ty), text = note
        ax.annotate(text, xy=(mdates.date2num(px), py), xytext=(mdates.date2num(tx), ty),
                    fontsize=10.5, color=INK, ha='left', va='center', zorder=6,
                    bbox=dict(boxstyle='round,pad=0.35', fc='white', ec='none', alpha=.92),
                    arrowprops=dict(arrowstyle='-', color=INK, lw=.9, shrinkA=2, shrinkB=2))

    fig.text(0.13, 0.965, title, fontsize=17.5, fontweight='bold', color=INK, va='top')
    fig.text(0.13, 0.905, subtitle, fontsize=12, color=INK, va='top')
    _key(fig, vmax, np.any(detected > vmax), missing.any())

    add_logo(fig, logo)
    return fig


def _key(fig, vmax, clipped, has_missing):
    """Colour scale with numbers, what blank and hatched mean, and how to read the grid."""
    bar = fig.add_axes([0.13, 0.81, 0.24, 0.022])
    extent = [0.5, 1.5, 0, 1] if vmax == 1 else [1, vmax, 0, 1]
    bar.imshow(np.linspace(1, vmax, 128)[None, :], aspect='auto', cmap=DETECTIONS,
               extent=extent)
    step = vmax / 4 if vmax % 4 == 0 and (vmax / 4) % 5 == 0 else (5 if vmax <= 20 else 10 if vmax <= 100 else 50)
    ticks = [1] + list(range(int(step), int(vmax) + 1, int(step)))
    if ticks[-1] != vmax:
        ticks.append(vmax)
    bar.set_xticks(ticks, [f'{t:g}' + ('+' if clipped and t == vmax else '') for t in ticks])
    bar.set_yticks([])
    bar.tick_params(length=3, labelsize=9.5, colors=INK, pad=3)
    for spine in bar.spines.values():
        spine.set_visible(False)
    fig.text(0.13, 0.845, 'Detections per 15 minutes', fontsize=10.5, color=INK,
             fontweight='bold', va='bottom')

    # Swatches: blank (day and night halves) and, if any, hatched.
    x = 0.43
    swatch = fig.add_axes([x, 0.81, 0.028, 0.022])
    swatch.add_patch(Rectangle((0, 0), .5, 1, color=DAY))
    swatch.add_patch(Rectangle((.5, 0), .5, 1, color=NIGHT))
    swatch.set_xlim(0, 1); swatch.set_ylim(0, 1); swatch.axis('off')
    fig.text(x + 0.036, 0.821, 'None detected', fontsize=10.5, color=INK, va='center')
    if has_missing:
        x = 0.62
        swatch = fig.add_axes([x, 0.81, 0.028, 0.022])
        swatch.add_patch(Rectangle((0, 0), 1, 1, facecolor='white', edgecolor=HATCH, hatch='////', lw=0))
        swatch.set_xlim(0, 1); swatch.set_ylim(0, 1); swatch.axis('off')
        fig.text(x + 0.036, 0.821, 'No recordings that day', fontsize=10.5, color=INK, va='center')
    fig.text(0.13, 0.745, 'Each column is one day. Each small square covers 15 minutes.',
             fontsize=11, color=INK, va='center')
