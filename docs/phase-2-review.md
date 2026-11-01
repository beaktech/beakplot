# Phase 2 review

Phase 1 was approved, including the grey-gap correction. The agreed rule is
unchanged: a day containing only false positives is unknown.

## Database reader

`read_database(path, tz=None, min_confidence=None, monitor_id=None)` returns plain
`Detection` records for the existing aggregation and chart functions. It
recognises both BirdNET-Go SQLite schemas, retains common names where available,
and adds confidence to the record model. No runtime dependencies were added.

It opens the file using an escaped file URI with `mode=ro`, enables `query_only`,
and reads within one transaction. The connection closes on success and failure.
It never creates a missing database or runs migrations. SQLite's normal WAL
handling is retained; `immutable=1` is not used because it could omit committed
records still in the WAL.

All species are loaded, so other retained records establish a recorded day with
zero detections of the selected species. False positives are excluded with
`NOT EXISTS`, preventing duplicate reviews from multiplying rows or restoring
a false positive. An optional confidence threshold is inclusive and applies to
recording coverage too. Secondary predictions and model contributions do not
increase detection counts.

Databases containing both primary schema tables are rejected as ambiguous.
Missing required columns, invalid timestamps, broken label references and
invalid confidence values produce descriptive errors. A missing review table
means there are no reviews; an existing but malformed review table is rejected.
Known incomplete v2 migration states and related-data migration errors are
rejected, since reviews or detections may not yet be fully copied.

## Checked against the actual source

Read from `~/Sites/birdnet-go`, at commit
`91618b8617f5de5fe89968f9d62ab92591f836dd`. Existing unrelated frontend changes in
that checkout were left untouched. These source files, rather than the plan's
schema summary, determined the reader:

| Source under `internal/` | Verified behaviour |
| --- | --- |
| `datastore/model.go`, `datastore/entities/note.go`, `datastore/entities/review.go` | Legacy `notes` contains `date`, `time`, names and confidence; `note_reviews.note_id` links `verified` reviews. |
| `datastore/mapper/detection.go` | Legacy date/time strings are formatted local clock values without offsets. |
| `datastore/v2/entities/detection.go` | V2 primary records are `detections`; use `id`, `label_id`, `detected_at` and `confidence`, not `legacy_id` or capture times. |
| `datastore/v2/entities/label.go`, `label_type.go` | Scientific names are in `labels`; label types distinguish species from sound classes. Common names are not a normal v2 label column. |
| `datastore/v2/entities/detection_review.go` | V2 reviews are in `detection_reviews`, linked by `detection_id`, with the same `verified` values. |
| `datastore/v2only/datastore.go` | `detected_at` is Unix **seconds**; `begin_time` and `end_time` use **milliseconds**. Common names are resolved outside the database. |
| `detection/species.go` | Older species labels may contain scientific name, common name and code separated by underscores; sound-class identities must remain whole. |
| `datastore/v2/manager.go`, `entities/migration_state.go`, `v2only/fresh_install.go` | SQLite v2 table names have no prefix; migrations use a separate file. Migration metadata has old singular and current plural table names. Fresh installs mark migration complete. |

V2 timestamps are converted individually using the requested time zone, including
historical daylight-saving offsets and date boundaries. No fixed current offset
is applied to a season's data. Legacy strings are preserved because the file
does not identify their original time zone. The heatmap must use that station's
zone. V2 common names remain empty when absent; no names are invented or fetched.

## Validation

79 tests pass with `.venv/bin/python -m pytest -q`, including the 26 phase 1 tests.
All database fixtures are small synthetic SQLite files built under pytest's
temporary directory. No tests read real backups, CSV exports or website data.

Coverage includes both schemas, reviewed/unreviewed detections, duplicate and
conflicting reviews, unknown versus zero days, confidence boundaries, ID scopes,
the seven-consecutive-day average, quarter-hour bins, multiple model labels,
secondary-prediction exclusion, missing reviews, malformed files and records,
incomplete migrations, date rollover and both daylight-saving transitions.
The read-only tests attempt a write through the actual reader connection and
confirm SQLite rejects it. They also check connection closure and that committed
uncheckpointed WAL records are visible without changing the database or WAL.

Environment: Python 3.15, Matplotlib 3.11.2, NumPy 2.5.4. Python 3.10+ remains the
declared minimum; package sources pass Python 3.10 syntax parsing, but this suite
has not been run on a Python 3.10 interpreter here.

## Real backup check and limits

Only one database was available under `~/BirdNET-Backups`: Kendal's
`database/20260903T183934Z.db`, alongside its WAL and SHM files. It has the v2
schema and a completed migration, but **zero detections, labels and reviews**.
The reader recognised it and returned an empty list successfully.

SHA-256 checksums of all three files were identical before and after the checks,
and no files were added to the backup directory. The checksum record is local
only, under ignored `.local/phase2/`. No real databases or detections were copied
into tests or committed.

This confirms real-file compatibility and read-only behaviour, not populated
real-data accuracy. Both populated schemas are exercised by synthetic tests;
there was no populated real legacy or v2 backup available for a stronger check.

Read one complete snapshot per station. Merging differing review histories or
legacy/v2 ID spaces is not supported. The reader currently returns an in-memory
list rather than a streaming cursor.

Phase 3 has not started. No blocking questions remain; CSV loading and the
command-line interface are outside this phase.
