"""Recreate the README charts from the autumn article's published aggregates.

Pass seasonal-2026.json from the Beak Tech website checkout. This reads aggregate
counts only; detection exports and databases are not needed or copied.
Source: https://beaktech.org/blog/listening-to-autumn
"""

import argparse
from datetime import date
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')

from beakplot import daily_counts, day_clock
from beakplot.cli import _save


def generate(source, output, logo=None):
    data = json.loads(source.read_text(encoding='utf-8'))
    dates = [date.fromisoformat(day) for day in data['dates']]
    period = f'{dates[0].day} {dates[0]:%B}–{dates[-1].day} {dates[-1]:%B %Y}'
    output.mkdir(parents=True, exist_ok=True)
    heatmap = day_clock(
        data['keswick_house_martin_quarter_hours'], dates, 54.60, -3.13,
        tz='Europe/London', logo=logo,
        title='House martins were detected most often just before sunset',
        subtitle=f'Northern Office monitor, Keswick · {period}',
        note=((date(2026, 8, 24), 20.2), (date(2026, 8, 2), 22.9),
              'The evening peak shifts earlier as sunset does'))
    _save(heatmap, output / 'heatmap.png')
    sites = ('northern-office', 'southern-office', 'kendal')
    series = {data['sites'][site]['location']: data['sites'][site]['daily']['house_martin']
              for site in sites}
    daily = daily_counts(series, dates, logo=logo,
                         title='House-martin detections through the summer',
                         subtitle=f'National Park office monitors · {period}',
                         annotate_last=('Kendal',))
    _save(daily, output / 'daily.png')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('aggregates', type=Path, help='published seasonal-2026.json')
    parser.add_argument('--out', type=Path, default=Path('.local/article'))
    parser.add_argument('--logo', type=Path, help='optional Beak Tech logo from the website checkout')
    args = parser.parse_args()
    generate(args.aggregates, args.out, args.logo)
