# Phase 1 review

Completed 31 October 2026. Phase 2 has not started.

Validation: 26 pytest tests pass on Python 3.15, Matplotlib 3.11.2 and NumPy
2.5.4. Editable installation builds and imports successfully. Package sources
also pass Python 3.10 syntax parsing; the suite has not run on Python 3.10 here.

The two original scripts were copied locally before extraction. Their drawing
code now lives in `src/dayclock/heatmap.py` and `src/dayclock/daily.py`, with plain
record aggregation in `data.py` and shared appearance in `style.py`. The package
has no fixed stations, species, date range, website paths or compulsory logo.
Python 3.10+ is declared; runtime dependencies are Matplotlib and NumPy.

## Article comparison

The ignored `.local/compare.py` reads the three original CSV exports from
`~/Downloads`, the original scripts and manual exclusions from
`~/Sites/beaktech/beak-tech`, and the published seasonal SVGs. It never calls the
original command-line entry point, which could overwrite the website's saved
aggregates. The website repository was not edited.

The comparison rebuilt the aggregates from CSV, rather than simply plotting
the saved JSON. The original aggregation matched `seasonal-2026.json` exactly.
The package matched every daily count for all five article species at all three
stations, every recording-coverage value, and all three quarter-hour arrays.
The article's manual exclusions, titles, annotations, logo, time zone, colour
limits, SVG salt and rasterisation resolution were supplied externally.

| Published SVG | Package comparison |
| --- | --- |
| `house-martin-keswick-heatmap.svg` | Byte-for-byte identical; PNG pixels identical too. |
| `robin-haverthwaite-heatmap.svg` | Byte-for-byte identical; PNG pixels identical too. |
| `house_martin-over-time.svg` | Only one grey gap band moves half a day left to align with its daily bar. |
| `robin-over-time.svg` | Only the same grey gap band correction. |
| `barn_swallow-over-time.svg` | Only the same grey gap band correction. |
| `swift-over-time.svg` | Same gap correction, plus pre-existing text/logo rendering differences described below. |

For **all four daily SVGs**, comparison against the original script regenerated
in the same environment finds exactly one changed SVG element: the grey
unknown-day path. Every bar, average line, axis, annotation and text element
otherwise matches that baseline. The corrected band moves 2.481081 SVG points
left, retaining its width of one day. It marks Haverthwaite's missing day.

The original script itself does not exactly reproduce the published swift SVG:
11 text elements have position differences (tick baselines under 0.001 points;
the two vertical axis labels move about 0.355 points), and the embedded logo is
43 × 36 rather than 44 × 37 pixels. No data paths or words differ. This isolates
those differences from the refactor; their original rendering settings are not
recorded, so the precise historical cause is unconfirmed. Embedded PNG pixels
were decoded when comparing SVGs, avoiding false differences from compression.
The published swift PNG differs more substantially, so it is not used to claim
an SVG match. The SVG comparison above is the acceptance evidence.

Local review artefacts:

- `.local/comparison/package/`: all six regenerated SVGs and PNGs.
- `.local/comparison/original/`: original-script baseline in the same environment.
- `.local/comparison.log`: aggregate and file comparison results.
- `.local/audit_svg.py`: element-level assertions separating the gap correction
  from the original swift rendering differences.
- `.local/originals/`: untouched copies of both starting scripts.

To repeat locally after installing dependencies:

```sh
MPLCONFIGDIR=.local/matplotlib MPLBACKEND=Agg PYTHONPATH=src \
  .venv/bin/python .local/compare.py > .local/comparison.log 2>&1
.venv/bin/python .local/audit_svg.py
```

These scripts refer to this machine's source paths and are deliberately ignored,
along with all generated charts. No real detection rows or aggregates are in
the commit. Tests use synthetic data only.

## Issues in the old scripts

- Daily gap shading was shifted: subtracting twelve hours from a `date` discards
  the hours. The shading is now centred on the bar's date, using datetimes.
- A single daily panel failed because Matplotlib returned a single axes object.
  A last-detection annotation also failed if there were no positive counts.
- De-duplication before review filtering could retain an unreviewed duplicate
  ahead of its false-positive copy. Any false-positive copy now excludes its ID.
  This has no effect on the article aggregates.
- The sun calculation used 365 in leap years too. NOAA specifies 366 for leap
  years; corrected without affecting the 2026 article. The old claim of roughly
  one-minute accuracy was too strong for a simple fractional-year approximation.
  See [NOAA's equations](https://gml.noaa.gov/grad/solcalc/solareqns.PDF).
- All-zero or unknown heatmaps called `nanmax` on an entirely empty detection
  array, emitting a warning. Empty detection grids now render without warnings.
- The rolling average previously assumed consecutive dates implicitly. The
  package rejects gaps, duplicates and reversed date lists explicitly.

The solar test uses an independent fixed reference: Greenwich, 21 June 2026,
sunrise 04:43 and sunset 21:21 at UTC+1 from the
[US Naval Observatory](https://aa.usno.navy.mil/api/rstt/oneday?date=2026-06-21&coords=51.4779,0&tz=1).
The retained approximation gives approximately 04:42 and 21:20, within the
two-minute test tolerance. Tests also check summer/winter offsets and another
time zone. There are no network calls in the test suite.

## Before phase 2

Please review the intentional grey-gap correction. There are no blocking input
questions. One policy to revisit if desired: a day containing only excluded
false positives remains unknown, as in the original scripts. Database support
will preserve this unless the owner chooses a separate recording-coverage rule.
