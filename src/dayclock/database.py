"""Read BirdNET-Go SQLite files without modifying the database.

Schema references and timestamp conventions are recorded in docs/phase-2-review.md.
Only primary detections count: secondary predictions and model contributions
are deliberately not joined, as they would multiply the observations.
"""

from contextlib import closing
from datetime import date, datetime, time, timezone
import math
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from .data import Detection


class DatabaseError(ValueError):
    """An unreadable, unsupported or inconsistent BirdNET-Go database."""


def _columns(connection, table, required):
    # All table names supplied here are fixed in this module, never user input.
    columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
    missing = set(required) - columns
    if missing:
        raise DatabaseError(f"{table}: missing columns {', '.join(sorted(missing))}")
    return columns


def _review_sql(connection, tables, table, foreign_key):
    if table not in tables:
        return "''", "1"
    _columns(connection, table, {foreign_key, "verified"})
    # EXISTS avoids duplicated detections even in an old file with duplicate
    # reviews. Any false-positive review wins over an unreviewed/correct copy.
    matching = f"FROM {table} r WHERE r.{foreign_key} = d.id"
    status = f"COALESCE((SELECT MAX(r.verified) {matching}), '')"
    retained = f"NOT EXISTS (SELECT 1 {matching} AND r.verified = 'false_positive')"
    return status, retained


def _check_migration(connection, tables):
    # Both names occur in upstream: migration_state was renamed in PR #2165.
    for table in ("migration_states", "migration_state"):
        if table not in tables:
            continue
        columns = _columns(connection, table, {"state"})
        error = "related_data_error" if "related_data_error" in columns else "''"
        for state, related_error in connection.execute(f"SELECT state, {error} FROM {table}"):
            if state not in ("idle", "completed") or related_error:
                raise DatabaseError("V2 migration is incomplete; use a completed database backup")


def _query(connection):
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "notes" in tables and "detections" in tables:
        raise DatabaseError("Ambiguous schema: both notes and detections tables are present")
    if "notes" in tables:
        columns = _columns(connection, "notes", {"id", "date", "time", "scientific_name", "confidence"})
        status, retained = _review_sql(connection, tables, "note_reviews", "note_id")
        common = "d.common_name" if "common_name" in columns else "''"
        return "legacy", f"""
            SELECT d.id, d.date, d.time, d.scientific_name, {common} AS common_name,
                   d.confidence, {status} AS review_status
            FROM notes d WHERE {retained}
        """
    if "detections" in tables:
        _columns(connection, "detections", {"id", "detected_at", "label_id", "confidence"})
        _columns(connection, "labels", {"id", "scientific_name", "label_type_id"})
        _columns(connection, "label_types", {"id", "name"})
        _check_migration(connection, tables)
        status, retained = _review_sql(connection, tables, "detection_reviews", "detection_id")
        return "v2", f"""
            SELECT d.id, d.detected_at, l.scientific_name, t.name AS label_type,
                   d.confidence, {status} AS review_status
            FROM detections d
            LEFT JOIN labels l ON l.id = d.label_id
            LEFT JOIN label_types t ON t.id = l.label_type_id
            WHERE {retained}
        """
    raise DatabaseError("Unrecognised BirdNET-Go schema: no notes or detections table")


def _detection(row, schema, tz, monitor_id):
    try:
        if row["id"] is None:
            raise ValueError("missing detection ID")
        scientific_name = row["scientific_name"]
        if not isinstance(scientific_name, str) or not scientific_name.strip():
            raise ValueError("missing scientific name or referenced label")
        confidence = float(row["confidence"])
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if schema == "legacy":
            day = date.fromisoformat(row["date"])
            clock = time.fromisoformat(row["time"])
            if clock.tzinfo is not None:
                raise ValueError("legacy time must be a local clock time without an offset")
            common_name = row["common_name"] or ""
        else:
            if not isinstance(row["detected_at"], int):
                raise ValueError("detected_at must be Unix seconds")
            local = datetime.fromtimestamp(row["detected_at"], timezone.utc).astimezone(tz)
            day, clock = local.date(), local.time()
            if row["label_type"] is None:
                raise ValueError("missing referenced label type")
            scientific_name = scientific_name.strip().replace("\r", "")
            common_name = ""
            # Older species labels can contain Scientific_Common_Code. Sound
            # classes such as power_tool retain their whole label as identity.
            if row["label_type"] == "species":
                parts = scientific_name.split("_", 2)
                scientific_name = parts[0]
                if len(parts) > 1:
                    common_name = parts[1]
                if not scientific_name.strip():
                    raise ValueError("missing scientific name in species label")
        return Detection(day, clock, scientific_name, str(row["id"]), monitor_id,
                         row["review_status"], common_name, confidence)
    except (ValueError, TypeError, OverflowError, OSError) as error:
        raise DatabaseError(f"Invalid {schema} detection {row['id']}: {error}") from error


def read_database(path, *, tz=None, min_confidence=None, monitor_id=None):
    """Return retained detections from an automatically recognised SQLite file.

    False positives are excluded before establishing recording coverage. All
    species are read so aggregation can distinguish unknown days from zero.
    An optional confidence threshold (0–1, inclusive) also filters coverage.

    V2 Unix seconds are converted to `tz` (IANA name or tzinfo), defaulting to
    the system time zone. Legacy local date/time strings are preserved: they
    contain no offset from which to convert to another time zone.

    IDs are scoped to the resolved file path unless `monitor_id` is supplied.
    Read one complete snapshot per station; merging review histories from
    different snapshots or legacy/v2 ID spaces is not supported.
    No secondary predictions or model contributions are counted.

    The connection uses mode=ro and query_only, honours SQLite WAL files and
    closes before returning. Missing paths are never created. Supply a complete
    backup (including its WAL when present), not an in-progress migration.
    """
    if min_confidence is not None and (
            not math.isfinite(min_confidence) or not 0 <= min_confidence <= 1):
        raise ValueError("min_confidence must be between 0 and 1")
    tz = ZoneInfo(tz) if isinstance(tz, str) else tz
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise IsADirectoryError(f"Not a database file: {path}")
    monitor_id = str(path) if monitor_id is None else monitor_id
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            connection.execute("BEGIN")
            schema, query = _query(connection)
            parameters = ()
            if min_confidence is not None:
                query += " AND d.confidence >= ?"
                parameters = (min_confidence,)
            query += " ORDER BY d.id"
            return [_detection(row, schema, tz, monitor_id)
                    for row in connection.execute(query, parameters)]
    except sqlite3.Error as error:
        raise DatabaseError(f"Cannot read SQLite database {path}: {error}") from error
