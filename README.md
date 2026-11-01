# Day clock

Seasonal bird detection charts, packaged from Beak Tech's autumn article.
Phase 1 provides Python functions; database readers and the command-line tool
come in later phases of [the plan](PLAN.md).

A detection is an automatic identification, not a bird. Counts do not measure
the number of individual birds or prove that a recorder ran continuously.

For development, use Python 3.10 or newer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest
```

`Detection` holds a local `date`, local `time`, scientific name, optional
detection ID, monitor ID and review status. `aggregate(records, dates, species)`
returns aligned `daily`, `quarter_hours` and `coverage` lists. Supply all species'
records so a recorded day with no detections of the chosen species can be zero.
Pass one station's records to aggregate that station separately.

- False positives and optional `(monitor_id, detection_id)` exclusions are
  removed. Detection IDs are de-duplicated within each monitor. A false-positive
  review on any copy wins; records without IDs are counted independently.
- Days with no retained records are unknown (`None`), never zero. This preserves
  the original scripts' conservative treatment of days containing only excluded
  records. A recorded day does not establish full-day uptime.
- The trailing average needs seven consecutive recorded days, including zero
  counts. Date lists must be consecutive and ascending.
- `day_clock(rows, dates, lat, lon, ...)` takes 96 quarter-hour counts per day,
  or `None`. Detection colours are opaque; zero cells reveal daylight or night;
  unknown days are hatched. Use the same `vmax` for comparable heatmaps.
- `daily_counts({label: counts, ...}, dates, ...)` draws one or more panels,
  with unknown days grey and independent vertical scales.

Both plotting functions return a Matplotlib figure, accept `title`, `subtitle`
and an optional `logo` image path, and leave global plotting settings unchanged.
Use `fig.savefig("chart.svg")` or `fig.savefig("chart.png", dpi=240)` and close
the figure when finished. The default subtitle explains what detections mean.

The heatmap accepts `tz="Europe/London"` or another IANA time zone; omitting it
uses the system's local time zone. Coordinates are used only for sunrise and
sunset. The original NOAA approximation is retained, with leap years corrected;
it is approximate to minutes, and polar dates without both sunrise and sunset
currently raise a clear error.

The [phase 1 comparison](docs/phase-1-review.md) records the article checks.
Real detections, local reproduction scripts and generated charts stay under
the ignored `.local/` directory or in their original read-only locations.
