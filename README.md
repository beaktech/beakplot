# Day clock

Seasonal bird detection charts, packaged from Beak Tech's autumn article.
The Python functions read BirdNET-Go SQLite databases and draw charts. The
command-line tool comes in phase 3 of [the plan](PLAN.md).

A detection is an automatic identification, not a bird. Counts do not measure
the number of individual birds or prove that a recorder ran continuously.

For development, use Python 3.10 or newer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest
```

`Detection` holds a local `date`, local `time`, scientific name, optional
detection ID, monitor ID, review status, common name and confidence.
`aggregate(records, dates, species)`
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

## Database input

```python
from dayclock import read_database

records = read_database("birdnet.db", tz="Europe/London", min_confidence=0.7)
```

`read_database` detects the legacy or v2 SQLite schema and returns `Detection`
records for all species, ready for `aggregate`. It opens the database with
`mode=ro` and `query_only`, then closes the connection before returning. Keep a
backup's WAL alongside its database when present; committed rows in the WAL
are included. Incomplete migrations and unsupported schemas raise
`DatabaseError`; a missing file is never created.

False positives are excluded, including when conflicting review copies exist.
Days containing only false positives remain unknown. `min_confidence` is
optional and inclusive (0–1); days containing only filtered-out records are
also unknown. Secondary predictions and model contributions are not counted
as additional detections.

Legacy date/time strings already contain local clock time and are kept as
stored. Set the heatmap's time zone to the station's zone. V2 timestamps are
Unix seconds and are converted using the requested zone, including historical
clock changes; the system's local zone is the default. No station time zone is
inferred from coordinates or database fields.

Legacy common names are preserved. V2 generally stores only scientific names;
common names are left empty unless an older combined species label contains
one. Non-species sound labels retain their identity and provide recording
coverage, just like other retained records.

By default, detection IDs are scoped to the resolved database path, keeping
different stations separate. `monitor_id` can supply an explicit station
identity instead. Read one complete snapshot per station; merging review
histories across snapshots is not supported. Legacy and v2 ID spaces also
differ and should not be combined as overlapping backups.

The [phase 2 review](docs/phase-2-review.md) records source references, tests and
the read-only backup check. CSV loading and the command-line interface are not
implemented in this phase.
