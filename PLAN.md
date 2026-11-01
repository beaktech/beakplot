# Day clock: plan

Subroutine: Beak Tech #128. Written 26 October 2026 for Codex to do the development work. The owner (Oli) reviews each phase.

## What we're building

Day clock is a small open-source tool that turns any [BirdNET-Go](https://github.com/tphakala/birdnet-go) station's detections into clear seasonal charts. It is aimed at hobbyists, reserves and researchers running BirdNET-Go who want to see how their birds change through the year.

It makes two charts, both already designed and used in the article [What autumn sounds like in the Lakes](https://beaktech.org/blog/listening-to-autumn):

1. **The day clock heatmap.** Detections of one species by date (columns) and time of day (15-minute squares), drawn over that place's real daylight and night. It shows at a glance whether a pattern belongs to dawn, day or dusk, and how it moves with the seasons.
2. **Daily counts.** Daily detections of one species with a seven-day average, for one or more stations, with days without recordings shown as unknown, never as zero.

Why it matters: nothing in the [BirdNET showroom](https://birdnet.cornell.edu/showroom/) turns BirdNET-Go data into seasonal charts. We want Day clock good enough to be listed there (Subroutine #130).

## Starting point (read these first)

These are in the Beak Tech website repo. Copy them in as the starting point; don't edit them there.

- `~/Sites/beaktech/beak-tech/scripts/dayclock.py`: the heatmap, `day_clock(rows, dates, lat, lon, ...)`. Its docstring lists design rules that must be kept.
- `~/Sites/beaktech/beak-tech/scripts/generate-seasonal-charts.py`: the daily-count charts, plus the aggregation from detection records. It is hard-coded to three National Park sites, five species and fixed dates, and reads a custom CSV export (`<site>-all-history-detections.csv`, with columns `monitor_id`, `detection_id`, `date_local`, `time_local`, `scientific_name`, `review_status`).
- The output: `~/Sites/beaktech/beak-tech/public/images/seasonal-2026/*.svg`. The new tool's output should look the same.

## Input: BirdNET-Go's own data

The tool must work from what a BirdNET-Go user already has, without our export scripts.

1. **BirdNET-Go's SQLite database (main input).** For the legacy schema, the `notes` table has `date`, `time`, `scientific_name`, `common_name`, `confidence` and more. Review status is in a separate reviews table, where `false_positive` records must be excluded. BirdNET-Go also has a newer v2 datastore with a different schema. **Check both against the BirdNET-Go source** in `~/Sites/birdnet-go` (`internal/datastore/model.go` and `internal/datastore/v2/`), rather than trusting this summary. Support both, detecting which one a file uses. Open the database read-only.
2. **A CSV** with at least date, time and scientific name (column names configurable), for people who export from elsewhere. This should also read our existing export format.
3. **Later, not in the first release:** BirdNET-Go's HTTP API (`/api/v2/...`), so it can chart a live station.

Real data to test against, read-only: `~/BirdNET-Backups/<monitor>/database/` holds backed-up BirdNET-Go databases. **Never commit any of it**, and don't put real detections in tests. Make small synthetic databases instead.

## Interface

A Python package with a command-line tool, installable with `pip install` / `pipx install`:

```
dayclock heatmap --db birdnet.db --species "Delichon urbicum" --from 2026-06-20 --to 2026-10-08 --lat 54.6 --lon -3.13 --out house-martin.svg
dayclock daily   --db keswick.db --db kendal.db --label Keswick --label Kendal --species "Erithacus rubecula" --out robin.svg
dayclock species --db birdnet.db        # lists species and counts, to help choose
```

- Output to SVG and PNG (by extension), with title and subtitle options. Common names come from the data where present.
- `--min-confidence`, and time zone (default: the system's, or `--tz Europe/London`).
- The latitude and longitude are only for sunrise and sunset. Say so in the help.
- The same functions are importable for people working in notebooks.

## Rules the charts keep

These come from the article's method note, and they are what make the charts honest:

- A detection is an automatic identification, not a bird. Say so in the README and in the default subtitle.
- Exclude records reviewed as false positives. De-duplicate detection IDs.
- A day with no records at all is **unknown** (hatched or grey), not zero. A species count is zero only on days with records of other species.
- The seven-day average needs seven consecutive days with records.
- Sunrise and sunset are calculated from location and date in local clock time. Keep the existing sun calculation unless it's wrong.
- `vmax` can be fixed so charts are comparable.

## Phases (stop after each for Oli's review)

1. **Package the existing code.** New package layout (`src/dayclock/`), `pyproject.toml`, the heatmap and daily-count functions taking plain data, and no hard-coded sites, species or dates. Regenerate the autumn article's charts from our existing CSV and confirm they match the published SVGs.
2. **BirdNET-Go database input,** both schemas, with tests on small synthetic databases.
3. **Command-line tool** as above, with a clear error for a wrong path, an unknown species or an empty date range.
4. **README and examples:** what it is, a screenshot of each chart, install, quick start, the honest-charts rules above, and credits (BirdNET by the Cornell Lab of Ornithology and Chemnitz University of Technology; BirdNET-Go by tphakala). MIT licence. Example images made from synthetic or our own published data only.
5. **Release prep:** tests passing in CI (GitHub Actions), version 0.1.0, and a changelog. **Don't publish to GitHub or PyPI.** Oli will do that.

## Ground rules

- Python 3.10+, with matplotlib, numpy and the standard library. Avoid heavy dependencies such as pandas unless there's a clear need.
- Tests with pytest. Every phase ends with the tests passing.
- British spelling in docs and messages (colour, analyse, recognise).
- Commit after each phase, with plain commit messages and no AI attribution lines. Don't push.
- Keep it small. This is a focused tool, not a dashboard. If something seems to need a web app, stop and ask.

## Out of scope for 0.1

- A hosted upload page (a possible later Beak Tech service).
- Reading BirdNET-Pi or BirdNET-Analyzer output (maybe later, via CSV).
- Reports combining many species. One species per chart is enough for now.
