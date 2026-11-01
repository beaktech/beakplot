# Phase 4 review

The owner approved phase 3 after independently checking all three CLI commands
against a populated v2 database of about 66,000 detections. This phase implements
the four requested follow-up fixes, then completes documentation and examples.

## Requested fixes

- **English names:** an offline lookup provides titles, species-list names and
  case-insensitive species matching when an input does not supply a common name.
  Recorded names have priority. The short alias `Robin` selects
  `Erithacus rubecula`; IOC's preferred display name is `European Robin`.
  Close-match suggestions include the common and scientific names. Names absent
  from a station's detections cannot be selected merely because they occur in
  the lookup.
- **Partial days:** when the latest retained data date is today in the selected
  time zone, the CLI ends before that day by default. `--include-partial` keeps
  it. This applies to all three commands and explicit `--to` values too; the
  help and README explain it. A today-only range offers the opt-in flag.
  Historical first and last days remain: detection records do not prove uptime.
- **Single-station footer:** only the grey-gap explanation is printed. The
  independent-scale explanation remains for charts with multiple panels.
- **Missing inputs:** both SQLite and CSV paths report
  `Database not found: <path>` without a raw Errno message or traceback.

The partial-day rule uses the same time zone as v2 timestamp conversion and
sunlight. With no `--tz`, it uses the system zone. Tests cover midnight across
zones, the system default, historical boundaries, explicit end dates, today-only
data and opt-in inclusion. It does not alter the Python readers or the explicit
date grids supplied to plotting functions.

## Name data and licence verification

Bundled 11,250 English species-name pairs extracted from the IOC World Bird List
v15.2 CoLDP archive published through GBIF. The publisher's
[GBIF record](https://www.gbif.org/dataset/c696e5ee-9088-4d11-bdae-ab88daffab78)
explicitly declares **CC BY 4.0**. The downloaded archive identifies version
15.2, an issue date of 25 October 2026, and `license: CC-BY`.

The source URL, version DOI, editors, publisher, retrieval date, SHA-256 and
transformations are recorded in the shipped
[IOC notice](../src/dayclock/resources/IOC-NOTICE.md). The extraction script is
`scripts/build_common_names.py`. The input archive remains local and ignored;
only the English name mapping is bundled. IOC names and spelling are preserved.
`Robin` is a documented Day clock search alias, not a modification of IOC's name.

Day clock's code, documentation and synthetic examples use the new MIT licence.
The data retains CC BY 4.0 attribution and terms; it is not relicensed under MIT.
Package metadata therefore declares `MIT AND CC-BY-4.0`. Both notices and the
lookup were confirmed in the built wheel. The build requirement is now
setuptools 77+ to support standard SPDX licence metadata; runtime dependencies
remain unchanged. No network access is needed for name lookup.

## Documentation and examples

The README now explains what the charts show, checkout installation with pip
or pipx, a quick start, all input/date/name behaviours, the honest-chart rules,
CSV mappings, notebook use, errors and limitations. Credits name BirdNET's
Cornell Lab of Ornithology and Chemnitz University of Technology teams,
BirdNET-Go by tphakala, IOC/IOU and the original Beak Tech chart design.

`examples/generate.py` creates deterministic synthetic records, recording gaps
and recorded zero days, and renders both chart types through the CLI. It reads
no real data. The README's two PNGs are those outputs, visibly labelled
synthetic. The script recreates CSV, SVG and PNG files under ignored
`.local/examples/`. Both images were visually checked.

## Validation and remaining scope

- 184 pytest tests pass, including all earlier tests and the new regressions.
- A wheel builds successfully and contains the lookup and both licence notices.
  Installation into a separate directory and CLI rendering from outside the
  checkout confirm the lookup works without editable-source access.
- Python 3.10 syntax parsing passes. Execution here used Python 3.15,
  Matplotlib 3.11.2 and NumPy 2.5.4; Python 3.10 execution remains untested here.
- No real detections, backups or exported station records were read or committed
  in this phase. No changes were made to the website or BirdNET-Go repositories.

No blocking questions remain. Phase 5 has not started: there is no CI workflow,
0.1.0 version bump, changelog or publication in this change.
