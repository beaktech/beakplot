"""Read local-clock detection CSVs, including the original article exports."""

import csv
from datetime import date, time
import math
from pathlib import Path

from .data import Detection, retained_records


COLUMNS = {
    "date": ("date_local", "date"),
    "time": ("time_local", "time"),
    "scientific_name": ("scientific_name",),
    "detection_id": ("detection_id", "id"),
    "monitor_id": ("monitor_id",),
    "review_status": ("review_status", "verified"),
    "common_name": ("common_name",),
    "confidence": ("confidence",),
}


def read_csv(path, *, columns=None, min_confidence=None):
    """Return retained Detection records from a UTF-8 (optionally BOM) CSV.

    `columns` maps Detection field names to CSV headers. Date, time and
    scientific name are required; other fields are optional. Dates/times are
    ISO local-clock values, as in the legacy database. Confidence is 0–1 and
    must be present on every row if a minimum is requested. Each file should
    describe one station; monitor IDs, when present, scope detection IDs.
    """
    if min_confidence is not None and (
            not math.isfinite(min_confidence) or not 0 <= min_confidence <= 1):
        raise ValueError("min_confidence must be between 0 and 1")
    columns = columns or {}
    if set(columns) - COLUMNS.keys():
        raise ValueError("Unrecognised CSV field mapping")
    path = Path(path).expanduser().resolve(strict=True)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        try:
            headers = reader.fieldnames or []
        except csv.Error as error:
            raise ValueError(f"{path}: CSV header: {error}") from error
        if not headers or len(set(headers)) != len(headers):
            raise ValueError(f"{path}: CSV needs a header row with unique column names")
        selected = {}
        for field, defaults in COLUMNS.items():
            selected[field] = columns.get(field, next((c for c in defaults if c in headers), None))
            if selected[field] not in headers and (
                    field in columns or field in ("date", "time", "scientific_name")
                    or (field == "confidence" and min_confidence is not None)):
                raise ValueError(f"{path}: missing CSV column for {field}")
        records = []
        try:
            for row in reader:
                try:
                    if None in row:
                        raise ValueError("more fields than column headers")
                    values = {field: (row.get(column) or "").strip() for field, column in selected.items()}
                    if not values["scientific_name"]:
                        raise ValueError("scientific name is empty")
                    day = date.fromisoformat(values["date"])
                    clock = time.fromisoformat(values["time"])
                    if clock.tzinfo is not None:
                        raise ValueError("CSV time must be local clock time without an offset")
                    score = float(values["confidence"]) if values["confidence"] else None
                    if score is not None and (not math.isfinite(score) or not 0 <= score <= 1):
                        raise ValueError("confidence must be between 0 and 1")
                    if score is None and min_confidence is not None:
                        raise ValueError("confidence is missing but --min-confidence was requested")
                    records.append(Detection(
                        day, clock, values["scientific_name"], values["detection_id"] or None,
                        values["monitor_id"] or str(path), values["review_status"],
                        values["common_name"], score))
                except ValueError as error:
                    raise ValueError(f"{path}: CSV line {reader.line_num}: {error}") from error
        except csv.Error as error:
            raise ValueError(f"{path}: CSV line {reader.reader.line_num}: {error}") from error
    return [r for r in retained_records(records)
            if min_confidence is None or r.confidence >= min_confidence]
