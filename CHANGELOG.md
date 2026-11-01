# Changelog

## 0.1.0 — prepared, not yet published

First release of BeakPlot. It was developed as Day clock and renamed before its first
PyPI release; the `dayclock` name was never published there.

- Heatmaps with 15-minute counts, local daylight, recording gaps and
  optional fixed colour scales; daily counts with a trailing seven-day average.
- Read-only support for BirdNET-Go's legacy and v2 SQLite schemas, plus CSV
  input with configurable column names.
- `heatmap`, `daily` and `species` commands, SVG/PNG output, time-zone and
  confidence options, and an importable Python API.
- False-positive exclusion, de-duplicated IDs and unknown days kept distinct
  from recorded zero days. Seven-day averages require consecutive recorded days.
- English names from the credited IOC v15.2 lookup, with recorded names taking
  priority. Case-insensitive scientific/common-name matching, unique trailing
  common names such as Swallow and Wren, and close-match suggestions. Short
  matches report the chosen species; ambiguous matches list the candidates.
- Omit today's final partial day by default; `--include-partial` keeps it.
- Clear errors for missing files, unknown species and empty date ranges.
- README charts regenerated from Beak Tech's published autumn aggregates,
  plus a separate synthetic example generator requiring no real data.
- MIT-licensed code by Beak Tech Community Interest Company; the bundled IOC
  lookup retains its CC BY 4.0 licence and attribution.
- Synthetic pytest coverage and GitHub Actions for Python 3.10 and the latest
  stable Python 3. No publishing or deployment steps.
