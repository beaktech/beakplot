# Phase 3 review

Phase 2 was approved. The owner independently checked a populated v2 database
with about 66,000 detections: counts matched exactly after excluding false
positives, and the heatmap rendered correctly across the October clock change.
That check was reported by the owner, not rerun against real data in this phase.

## Implemented

The package installs a `dayclock` command, also available as
`python -m dayclock`, with `heatmap`, `daily` and `species` subcommands.
No new dependencies were added.

- Both SQLite schemas use the existing read-only reader. The CLI also includes
  the plan's CSV input, since the remaining phases cover documentation and
  release preparation. CSV header names are configurable, and the original
  article export format is recognised automatically.
- Date bounds are inclusive. Each omitted bound defaults independently to the
  first or last retained date across all selected inputs and all species.
  Review and confidence filtering happen first. Multiple daily panels share
  this date grid; one station can have unknown days where another has records.
- False-positive-only days remain unknown. De-duplication and false-positive
  exclusion were extracted unchanged into a shared helper so CSV input,
  species listings and aggregation follow the same rules.
- Unknown species suggest close matches from scientific and common names.
  Scientific names and unambiguous common names match without regard to case.
  Known species with no detections inside an otherwise recorded range give
  zero counts; ranges with no retained records of any species give an error.
- Wrong paths, malformed files, invalid date ranges, time zones, scores,
  coordinates, labels and output formats produce concise errors without a
  traceback. Runtime errors return status 2. The CLI never creates an input
  database or overwrites one with chart output, including through a hard link.
- `species` lists names and retained detection counts as tab-separated columns.
  `daily` supports several labelled stations. `heatmap` takes one station and
  coordinates, explicitly described in help as used only for sunrise/sunset.
- SVG and PNG output support title/subtitle options. Default titles use a
  common name where present; the default subtitle explains that detections
  are automatic identifications, not individual birds. Output is rendered to
  a temporary file beside its destination and replaced after success, keeping
  an existing chart intact if rendering fails.

The CSV reader is also importable as `read_csv`. It accepts UTF-8 with or without
a BOM, optional IDs, monitor IDs, review status, common names and confidence.
One file represents one station. Files with several retained monitor IDs are
rejected rather than silently combining stations. SQLite and CSV sources are
separate CLI alternatives, and a supplied file cannot appear twice.

## Layout corrections found during CLI checks

Visual review of synthetic output found overlapping date labels and footer
text in the one-station daily chart. Its bottom margin is now larger; the
existing two- and three-panel layout is unchanged.

Very short heatmap periods put fixed-offset sunlight labels outside the figure.
Offsets now shrink for short ranges; the 111-day article range keeps the same
offsets. The colour key also supports `--vmax 1` without a singular-axis warning
and labels a fractional/non-round maximum, including the clipping `+` indicator.
The article's round colour limits and layout are unchanged by these adjustments.

## Validation

163 pytest tests pass, including all earlier tests. New checks use only small
synthetic SQLite files and CSVs. They cover default/partial/explicit date bounds,
multi-station coverage, known zero counts, species suggestions, ambiguity,
confidence filters, duplicates, CSV mappings and error line numbers, invalid
options, missing inputs, output protection and real subprocess SVG/PNG rendering
with both database schemas. A v2 CLI heatmap also exercises the October clock
change with `Europe/London`.

The editable package was reinstalled successfully. The installed `dayclock`
command was exercised separately for species counts and SVG output; module
invocation is exercised by tests. Synthetic PNG heatmap and daily output were
visually inspected. Local review inputs and output are ignored under
`.local/phase3/`; no real detections were read or committed during phase 3.

Checks used Python 3.15, Matplotlib 3.11.2 and NumPy 2.5.4. Source syntax was
checked for Python 3.10 compatibility; tests have not run under Python 3.10 here.

## Before phase 4

No blocking questions. Full release documentation, example images, credits and
the MIT licence remain for phase 4. This phase does not add CI, change the
version to 0.1.0, publish or push anything.
