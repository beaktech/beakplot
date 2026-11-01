"""Command-line charts and species counts from local detection files."""

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from difflib import get_close_matches
import math
import os
from pathlib import Path
import sys
import tempfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .csv_input import read_csv
from .data import aggregate, retained_records
from .database import read_database
from .daily import daily_counts
from .heatmap import day_clock
from .names import common_name, preferred_names
from .style import DEFAULT_SUBTITLE, STYLE


def _date(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except ValueError:
        raise argparse.ArgumentTypeError("use a date in YYYY-MM-DD format") from None


def _number(minimum, maximum=None):
    def parse(value):
        try:
            number = float(value)
        except ValueError:
            raise argparse.ArgumentTypeError("use a number") from None
        if not math.isfinite(number) or number < minimum or (maximum is not None and number > maximum):
            bounds = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
            raise argparse.ArgumentTypeError(f"must be finite and {bounds}")
        return number
    return parse


def _zone(value):
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise argparse.ArgumentTypeError(f"unknown time zone {value!r}; use an IANA name such as Europe/London") from None


def _parser():
    parser = argparse.ArgumentParser(prog="beakplot", description="Seasonal bird detection charts.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, description in (("heatmap", "Detections by date and time over local daylight"),
                              ("daily", "Daily detections and a seven-day average"),
                              ("species", "List species and retained detection counts")):
        command = commands.add_parser(name, help=description, description=description)
        sources = command.add_mutually_exclusive_group(required=True)
        sources.add_argument("--db", action="append", type=Path, help="BirdNET-Go SQLite file; repeat for daily/species")
        sources.add_argument("--csv", action="append", type=Path, help="Detection CSV; repeat for daily/species (one station per file)")
        command.add_argument("--from", dest="start", type=_date, metavar="YYYY-MM-DD",
                             help="first day, inclusive; default: first retained date across all inputs")
        command.add_argument("--to", dest="end", type=_date, metavar="YYYY-MM-DD",
                             help="last day, inclusive; default: last retained date across all inputs")
        command.add_argument("--include-partial", action="store_true",
                             help="keep the last recorded day when it is today in --tz (system zone by default); "
                                  "today is otherwise excluded, even with --to")
        command.add_argument("--min-confidence", type=_number(0, 1), metavar="SCORE",
                             help="minimum confidence, inclusive (0–1); default: retain all scores")
        command.add_argument("--tz", type=_zone, metavar="ZONE",
                             help="time zone for v2 timestamps and sunlight; default: system local zone. "
                                  "Legacy/CSV clock times are kept as stored")
        csv_options = command.add_argument_group("CSV columns", "Optional header overrides; dates and times are local clock values")
        for option, field in (("date", "date"), ("time", "time"), ("species", "scientific_name"),
                              ("id", "detection_id"), ("monitor", "monitor_id"),
                              ("review", "review_status"), ("common-name", "common_name"),
                              ("confidence", "confidence")):
            csv_options.add_argument(f"--{option}-column", dest=f"column_{field}", metavar="HEADER")
        if name == "species":
            continue
        command.add_argument("--species", required=True,
                             help="scientific name, English common name or unique ending such as Swallow "
                                  "(case-insensitive); short matches report the chosen species")
        command.add_argument("--out", required=True, type=Path, help="output .svg or .png file (parent directory must exist)")
        command.add_argument("--title", help="chart title; default uses the common name where available")
        command.add_argument("--subtitle", default=DEFAULT_SUBTITLE, help="chart subtitle")
        if name == "daily":
            command.add_argument("--label", action="append", help="station label; supply one per input in the same order")
        else:
            command.add_argument("--lat", required=True, type=_number(-90, 90), help="latitude, used only for sunrise and sunset")
            command.add_argument("--lon", required=True, type=_number(-180, 180), help="longitude, used only for sunrise and sunset")
            command.add_argument("--vmax", type=_number(1), help="fixed colour-scale maximum for comparable heatmaps")
    return parser


def _load(args):
    paths = args.db or args.csv
    if args.command == "heatmap" and len(paths) != 1:
        raise ValueError("heatmap needs exactly one input file")
    resolved = []
    for path in paths:
        try:
            resolved.append(path.expanduser().resolve(strict=True))
        except FileNotFoundError:
            raise ValueError(f"Database not found: {path.expanduser()}") from None
    if any(a.samefile(b) for i, a in enumerate(resolved) for b in resolved[i + 1:]):
        raise ValueError("The same input file was supplied more than once")
    columns = {key.removeprefix("column_"): value for key, value in vars(args).items()
               if key.startswith("column_") and value is not None}
    if args.db and columns:
        raise ValueError("CSV column options require --csv")
    if args.command != "species":
        output = args.out.expanduser()
        if output.suffix.lower() not in (".svg", ".png"):
            raise ValueError("Output file must end in .svg or .png")
        if not output.parent.is_dir():
            raise ValueError(f"Output directory does not exist: {output.parent}")
        if output.is_dir():
            raise ValueError(f"Output path is a directory: {output}")
        if any(output.resolve() == p or (output.exists() and output.samefile(p)) for p in resolved):
            raise ValueError("Output must not overwrite an input file")
    if args.command == "daily":
        labels = args.label if args.label is not None else [p.stem for p in paths]
        if len(labels) != len(paths):
            raise ValueError("Supply exactly one --label per input file, in the same order")
        if any(not label.strip() for label in labels) or len(set(labels)) != len(labels):
            raise ValueError("Station labels must be non-empty and unique; use --label for matching filenames")
        args.labels = labels
    datasets = []
    for path in resolved:
        if args.db:
            rows = read_database(path, tz=args.tz, min_confidence=args.min_confidence)
        else:
            rows = read_csv(path, columns=columns, min_confidence=args.min_confidence)
            if len({r.monitor_id for r in rows}) > 1:
                raise ValueError(f"{path}: CSV contains multiple monitors; supply one station per file")
        datasets.append(list(retained_records(rows)))
    return datasets


def _species(rows, query):
    query = query.strip()
    key = query.casefold()
    scientific = {r.scientific_name for r in rows}
    exact = sorted(name for name in scientific if name.casefold() == key)
    if len(exact) == 1:
        return exact[0]
    recorded = defaultdict(set)
    for row in rows:
        if row.common_name:
            recorded[row.common_name.casefold()].add(row.scientific_name)
    # An exact recorded name takes priority even over another species' bundled
    # name. Ambiguity in recorded names still needs a scientific name.
    names = defaultdict(set)
    for name in scientific:
        for label in (name, common_name(name)):
            names[label.casefold()].add(name)
    for label, species in recorded.items():
        names[label].update(species)
    if key in recorded:
        names[key] = recorded[key]
    display = preferred_names(rows)

    def describe(matches):
        return ', '.join(repr(display[s]) + ' (' + s + ')' for s in matches)

    matches = sorted(names.get(key, ()))
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ValueError(f"Ambiguous species {query!r}; use a scientific name: {describe(matches)}")
    # Match whole trailing words, using recorded names before IOC fallbacks.
    # Build from present species only; the lookup cannot introduce a species.
    endings = defaultdict(set)
    for name in scientific:
        labels = [label for label, species in recorded.items() if name in species]
        if not labels and common_name(name) != name:
            labels = [common_name(name).casefold()]
        for label in labels:
            words = label.split()
            for i in range(1, len(words)):
                endings[' '.join(words[i:])].add(name)
    matches = sorted(endings.get(key, ()))
    if len(matches) == 1:
        print(f"Matched {query!r} to {describe(matches)}.", file=sys.stderr)
        return matches[0]
    if matches:
        raise ValueError(f"Ambiguous species {query!r}; use a full name: {describe(matches)}")
    for label, species in endings.items():
        names[label].update(species)
    close = get_close_matches(key, sorted(names), n=3, cutoff=.55)
    suggestions = sorted({species for name in close for species in names[name]})[:3]
    hint = f" Did you mean {describe(suggestions)}?" if suggestions else ""
    raise ValueError(f"Unknown species {query!r} in retained data.{hint} Use 'beakplot species' to list available names.")


def _today(tz):
    return datetime.now(tz).date()


def _range(rows, start, end, *, tz=None, include_partial=False):
    if start is not None and end is not None and start > end:
        raise ValueError("Empty date range: --from must be on or before --to")
    if not rows:
        raise ValueError("No retained detections in the input files after review/confidence filtering")
    start = start if start is not None else min(r.date for r in rows)
    last = max(r.date for r in rows)
    end = end if end is not None else last
    partial = not include_partial and last == _today(tz) and end >= last
    if partial:
        end = last - timedelta(days=1)
    if start > end or not any(start <= r.date <= end for r in rows):
        hint = "; today is excluded by default, use --include-partial to keep it" if partial else ""
        raise ValueError(f"Empty date range: no retained records from {start} to {end}{hint}")
    if end == date.max:
        raise ValueError("The last date must be before 9999-12-31")
    if partial:
        print(f"Excluding today's partial day ({last}); use --include-partial to keep it.", file=sys.stderr)
    return start, end


def _list_species(rows):
    counts = Counter(r.scientific_name for r in rows)
    display = preferred_names(rows)
    print("Scientific name\tCommon name\tDetections")
    for name in sorted(counts):
        label = display[name] if display[name] != name else ""
        print(f"{name}\t{label}\t{counts[name]}")


def _save(fig, output):
    """Replace the requested output only after a complete render succeeds."""
    import matplotlib.pyplot as plt
    output = output.expanduser()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=output.suffix, delete=False) as handle:
            temporary = Path(handle.name)
        fmt = output.suffix.lower().lstrip(".")
        options = {"metadata": {"Date": None, "Creator": "BeakPlot"}} if fmt == "svg" else {}
        with plt.rc_context(STYLE):
            fig.savefig(temporary, format=fmt, dpi=200 if fmt == "svg" else 240,
                        facecolor="white", **options)
        os.replace(temporary, output)
    finally:
        plt.close(fig)
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    """Run a command, returning zero on success and two for input/output errors."""
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        datasets = _load(args)
        rows = [row for dataset in datasets for row in dataset]
        start, end = _range(rows, args.start, args.end, tz=args.tz, include_partial=args.include_partial)
        if args.command == "species":
            _list_species([r for r in rows if start <= r.date <= end])
            return 0
        species = _species(rows, args.species.strip())
        dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        name = preferred_names(rows)[species]
        import matplotlib
        matplotlib.use("Agg")
        if args.command == "heatmap":
            counts = aggregate(datasets[0], dates, species)
            fig = day_clock(counts.quarter_hours, dates, args.lat, args.lon, tz=args.tz,
                            vmax=args.vmax, title=args.title if args.title is not None else f"{name}: detections by date and time",
                            subtitle=args.subtitle)
        else:
            series = {label: aggregate(dataset, dates, species).daily
                      for label, dataset in zip(args.labels, datasets)}
            fig = daily_counts(series, dates, title=args.title if args.title is not None else f"{name}: daily detections",
                               subtitle=args.subtitle)
        _save(fig, args.out)
        print(f"Saved {args.out} ({start} to {end})")
        return 0
    except (OSError, ValueError) as error:
        print(f"beakplot: error: {error}", file=sys.stderr)
        return 2
