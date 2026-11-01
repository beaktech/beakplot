"""Daily-count figures, adapted from generate-seasonal-charts.py."""

from datetime import datetime, time, timedelta

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, StrMethodFormatter
import numpy as np

from .data import trailing_mean, validate_dates
from .style import DEFAULT_SUBTITLE, add_logo, from_top, styled


@styled
def daily_counts(series, dates, *, title="Daily detections",
                 subtitle=DEFAULT_SUBTITLE, annotate_last=(), logo=None):
    """Return a figure from {label: daily counts}; None means unknown.

    `dates` must be consecutive. `annotate_last` names panels whose last
    positive day should be labelled. Each panel has its own vertical scale.
    """
    validate_dates(dates)
    if not series:
        raise ValueError("Provide at least one series")
    if any(len(values) != len(dates) for values in series.values()):
        raise ValueError("Provide one daily count per date in each series")
    fig, axes = plt.subplots(len(series), 1, figsize=(9, 3 + 1.8 * len(series)), sharex=True, squeeze=False)
    compact = len(series) == 2
    bottom = .16 if len(series) == 1 else .13 if compact else .10
    fig.subplots_adjust(left=.12, right=.97, top=from_top(fig, 136), bottom=bottom, hspace=.48)
    fig.suptitle(title, x=.12, y=from_top(fig, 18), va='top', ha='left', fontsize=21, fontweight='bold')
    fig.text(.12, from_top(fig, 54), subtitle, va='top', fontsize=12)
    fig.legend(handles=[Line2D([0], [0], color='#9abcae', lw=5, label='Daily detections'),
                        Line2D([0], [0], color='#bd6439', lw=2.5, label='Trailing 7-day average')],
               loc='upper left', bbox_to_anchor=(.12, from_top(fig, 84)), borderaxespad=0, ncol=2, frameon=False, fontsize=11)
    for ax, (location, counts) in zip(axes.flat, series.items()):
        values = np.array([np.nan if n is None else n for n in counts], dtype=float)
        if np.any(np.isinf(values)) or np.any(values < 0):
            raise ValueError("Daily counts must be non-negative or unknown")
        average = trailing_mean(values, dates)
        ax.bar(dates, values, width=.9, color='#9abcae', linewidth=0, zorder=2)
        ax.plot(dates, average, color='#bd6439', lw=2.2, zorder=3)
        for day, value in zip(dates, values):
            if np.isnan(value):
                ax.axvspan(datetime.combine(day, time()) - timedelta(hours=12),
                           datetime.combine(day, time()) + timedelta(hours=12), color='#eceef1', lw=0)
        ax.set_title(location, loc='left', fontsize=14, fontweight='bold', pad=8)
        ax.set_ylabel('Detections / day', fontsize=11)
        ax.set_ylim(bottom=0)
        if location in annotate_last and np.any(values > 0):
            last = np.flatnonzero(values > 0)[-1]
            ax.annotate(dates[last].strftime('%-d %b'),
                        xy=(dates[last], values[last]), xytext=(-30, 22),
                        textcoords='offset points', ha='right', fontsize=9,
                        arrowprops={'arrowstyle': '-', 'color': '#667789', 'lw': .8})
        ax.yaxis.set_major_locator(MaxNLocator(nbins=3, integer=True))
        ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
        ax.grid(axis='y', color='#e8ecee', zorder=0)
        ax.tick_params(length=0, pad=7)
        ax.set_xlim(dates[0], dates[-1] + timedelta(days=1))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    fig.text(.12, .047, 'Each panel has its own vertical scale. Grey = no records that day.', fontsize=9)
    add_logo(fig, logo)
    return fig
