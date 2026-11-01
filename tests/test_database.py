"""Small synthetic databases following BirdNET-Go's actual storage columns."""

from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
import hashlib
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from dayclock import DatabaseError, aggregate, read_database, trailing_mean
import dayclock.database as database


# Only columns relevant to the reader are needed; unrelated source/model/audio
# columns are included to guard against confusing IDs or timestamp units.
LEGACY = """
CREATE TABLE notes (
    id INTEGER PRIMARY KEY, source_node TEXT, date TEXT, time TEXT,
    scientific_name TEXT, common_name TEXT, confidence REAL
);
CREATE TABLE note_reviews (
    id INTEGER PRIMARY KEY, note_id INTEGER NOT NULL, verified TEXT,
    FOREIGN KEY (note_id) REFERENCES notes(id)
);
CREATE TABLE results (id INTEGER PRIMARY KEY, note_id INTEGER, species TEXT, confidence REAL);
"""
V2 = """
CREATE TABLE label_types (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE labels (
    id INTEGER PRIMARY KEY, scientific_name TEXT NOT NULL, model_id INTEGER NOT NULL,
    label_type_id INTEGER NOT NULL, taxonomic_class_id INTEGER
);
CREATE TABLE detections (
    id INTEGER PRIMARY KEY, model_id INTEGER NOT NULL, label_id INTEGER NOT NULL,
    source_id INTEGER, detected_at INTEGER NOT NULL, begin_time INTEGER,
    end_time INTEGER, confidence REAL NOT NULL, legacy_id INTEGER
);
CREATE TABLE detection_reviews (
    id INTEGER PRIMARY KEY, detection_id INTEGER NOT NULL, verified TEXT NOT NULL,
    FOREIGN KEY (detection_id) REFERENCES detections(id)
);
CREATE TABLE detection_predictions (id INTEGER PRIMARY KEY, detection_id INTEGER, label_id INTEGER);
CREATE TABLE detection_model_contributions (id INTEGER PRIMARY KEY, detection_id INTEGER, model_id INTEGER);
INSERT INTO label_types VALUES (1, 'species'), (2, 'mechanical');
INSERT INTO labels VALUES (1, 'Species alpha', 1, 1, 1), (2, 'Species beta', 1, 1, 1);
"""


@pytest.fixture(params=["legacy", "v2"])
def station(request, tmp_path):
    schema = request.param
    path = tmp_path / 'station #?%.db'
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(LEGACY if schema == "legacy" else V2)
    return path, schema


def add(connection, schema, identity, day, clock="06:15:00", *, species=1, confidence=.8, review=None):
    if schema == "legacy":
        connection.execute("INSERT INTO notes VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (identity, 'recorder', day, clock, f'Species {"alpha" if species == 1 else "beta"}',
                            'Synthetic bird', confidence))
    else:
        epoch = int(datetime.fromisoformat(f"{day}T{clock}").replace(tzinfo=timezone.utc).timestamp())
        connection.execute("INSERT INTO detections VALUES (?, 1, ?, 1, ?, ?, ?, ?, ?)",
                           (identity, species, epoch, epoch * 1000, (epoch + 3) * 1000, confidence, 999))
    if review is not None:
        table = 'note_reviews' if schema == 'legacy' else 'detection_reviews'
        connection.execute(f"INSERT INTO {table} VALUES (?, ?, ?)", (identity, identity, review))


def populate(path, schema):
    with closing(sqlite3.connect(path)) as c, c:
        add(c, schema, 1, '2025-04-01', review='false_positive')
        add(c, schema, 2, '2025-04-02', species=2)
        add(c, schema, 3, '2025-04-03', review='correct')
        add(c, schema, 4, '2025-04-03', clock='06:29:59')
        add(c, schema, 5, '2025-04-03', clock='06:30:00', confidence=.4)


def test_read_and_aggregate_preserves_unknown_zero_bins_and_metadata(station):
    path, schema = station
    populate(path, schema)
    rows = read_database(path, tz='UTC')
    assert [r.detection_id for r in rows] == ['2', '3', '4', '5']
    assert rows[1].review_status == 'correct'
    assert rows[1].confidence == .8
    assert rows[1].common_name == ('Synthetic bird' if schema == 'legacy' else '')
    assert all(r.monitor_id == str(path.resolve()) for r in rows)
    dates = [date(2025, 4, 1) + timedelta(days=i) for i in range(4)]
    counts = aggregate(rows, dates, 'Species alpha')
    assert counts.daily == [None, 0, 3, None]
    assert counts.coverage == [None, 1, 3, None]
    assert counts.quarter_hours[0] is None
    assert counts.quarter_hours[1] == [0] * 96
    assert counts.quarter_hours[2][25:27] == [2, 1]


def test_confidence_boundary_and_no_filtered_records_means_unknown(station):
    path, schema = station
    with closing(sqlite3.connect(path)) as c, c:
        for identity, score in enumerate([.79, .8, .81], 1):
            add(c, schema, identity, f'2025-04-0{identity}', confidence=score)
    rows = read_database(path, min_confidence=.8, tz='UTC')
    counts = aggregate(rows, [date(2025, 4, i) for i in (1, 2, 3)], 'Species alpha')
    assert counts.daily == [None, 1, 1]
    assert len(read_database(path, min_confidence=0)) == 3
    assert read_database(path, min_confidence=1) == []


def test_duplicate_reviews_cannot_multiply_or_restore_false_positives(station):
    path, schema = station
    populate(path, schema)
    table = 'note_reviews' if schema == 'legacy' else 'detection_reviews'
    with closing(sqlite3.connect(path)) as c, c:
        c.executemany(f"INSERT INTO {table} VALUES (?, ?, ?)",
                      [(10, 1, 'correct'), (11, 3, 'correct'), (12, 3, 'correct')])
        if schema == 'legacy':
            c.executemany("INSERT INTO results VALUES (?, 3, 'Species beta', .7)", [(1,), (2,)])
        else:
            c.executemany("INSERT INTO detection_predictions VALUES (?, 3, 2)", [(1,), (2,)])
            c.executemany("INSERT INTO detection_model_contributions VALUES (?, 3, ?)", [(1, 1), (2, 2)])
    assert [r.detection_id for r in read_database(path)] == ['2', '3', '4', '5']


def test_overlapping_backups_and_separate_monitors(station, tmp_path):
    path, schema = station
    populate(path, schema)
    other = tmp_path / 'other.db'
    other.write_bytes(path.read_bytes())
    day = [date(2025, 4, 3)]
    # Different files have separate identities unless the caller links them.
    both = read_database(path, tz='UTC') + read_database(other, tz='UTC')
    assert aggregate(both, day, 'Species alpha').daily == [6]
    both = read_database(path, monitor_id='station', tz='UTC') + read_database(other, monitor_id='station', tz='UTC')
    assert aggregate(both, day, 'Species alpha').daily == [3]


def test_false_positive_day_breaks_seven_day_average(station):
    path, schema = station
    dates = [date(2025, 4, 1) + timedelta(days=i) for i in range(15)]
    with closing(sqlite3.connect(path)) as c, c:
        for i, day in enumerate(dates):
            add(c, schema, i + 1, day.isoformat(), review='false_positive' if i == 7 else None)
    counts = aggregate(read_database(path, tz='UTC'), dates, 'Species alpha')
    average = trailing_mean(counts.daily, dates)
    assert average[6] == average[14] == 1
    assert np.isnan(average[7:14]).all()


def test_empty_database_and_absent_review_table(station):
    path, schema = station
    assert read_database(path) == []
    with closing(sqlite3.connect(path)) as c, c:
        c.execute('DROP TABLE ' + ('note_reviews' if schema == 'legacy' else 'detection_reviews'))
        add(c, schema, 1, '2025-04-01')
    assert len(read_database(path)) == 1


def test_read_only_connection_and_closure_on_success_and_error(station, monkeypatch):
    path, schema = station
    populate(path, schema)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    connect = sqlite3.connect
    connections = []

    def checked_connect(database_uri, **kwargs):
        assert database_uri == path.resolve().as_uri() + '?mode=ro'
        assert kwargs['uri'] is True
        c = connect(database_uri, **kwargs)
        connections.append(c)
        # mode=ro itself prevents writes, even before query_only is enabled.
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            c.execute('CREATE TABLE forbidden (id INTEGER)')
        return c

    monkeypatch.setattr(database.sqlite3, 'connect', checked_connect)
    assert read_database(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        connections[-1].execute('SELECT 1')
    with closing(connect(path)) as c, c:
        c.execute('DROP TABLE ' + ('notes' if schema == 'legacy' else 'labels'))
    with pytest.raises(DatabaseError):
        read_database(path)
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        connections[-1].execute('SELECT 1')


def test_uncheckpointed_wal_rows_are_visible(station):
    path, schema = station
    with closing(sqlite3.connect(path)) as writer:
        assert writer.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
        writer.execute('PRAGMA wal_autocheckpoint=0')
        add(writer, schema, 1, '2025-04-01')
        writer.commit()
        wal = Path(str(path) + '-wal')
        assert wal.stat().st_size > 0
        before = (path.read_bytes(), wal.read_bytes())
        assert len(read_database(path, tz='UTC')) == 1
        assert before == (path.read_bytes(), wal.read_bytes())


def make_v2(tmp_path):
    path = tmp_path / 'v2.db'
    with closing(sqlite3.connect(path)) as c:
        c.executescript(V2)
    return path


def test_v2_date_rollover_and_both_sides_of_clock_changes(tmp_path, monkeypatch):
    path = make_v2(tmp_path)
    instants = ['2025-03-30T00:30:00', '2025-03-30T01:30:00',
                '2025-06-20T23:45:00', '2025-10-26T00:30:00', '2025-10-26T01:30:00']
    with closing(sqlite3.connect(path)) as c, c:
        for i, stamp in enumerate(instants, 1):
            day, clock = stamp.split('T')
            add(c, 'v2', i, day, clock)
    rows = read_database(path, tz=ZoneInfo('Europe/London'))
    assert [r.time.hour for r in rows] == [0, 2, 0, 1, 1]
    assert rows[2].date == date(2025, 6, 21)
    # The repeated autumn hour contains two distinct detection IDs.
    assert [r.time.fold for r in rows[-2:]] == [0, 1]
    counts = aggregate(rows, [date(2025, 10, 26)], 'Species alpha')
    assert counts.daily == [2]
    assert counts.quarter_hours[0][6] == 2
    # None uses the system zone's rules at each instant, not today's offset.
    import time as system_time
    if hasattr(system_time, 'tzset'):
        with monkeypatch.context() as m:
            m.setenv('TZ', 'Europe/London')
            system_time.tzset()
            try:
                local = read_database(path)
                assert [(r.date, r.time) for r in local] == [(r.date, r.time) for r in rows]
            finally:
                m.undo()
                system_time.tzset()


def test_legacy_times_are_local_and_not_shifted(tmp_path):
    path = tmp_path / 'legacy.db'
    with closing(sqlite3.connect(path)) as c:
        c.executescript(LEGACY)
    populate(path, 'legacy')
    a = read_database(path, tz='Pacific/Auckland')
    b = read_database(path, tz='UTC')
    assert a == b
    assert a[0].time == time(6, 15)


def test_v2_species_labels_across_models_and_non_species_underscores(tmp_path):
    path = make_v2(tmp_path)
    with closing(sqlite3.connect(path)) as c, c:
        c.executescript("""
            INSERT INTO labels VALUES (3, ' Species alpha_Synthetic bird_code\r', 2, 1, 1);
            INSERT INTO labels VALUES (4, 'power_tool', 2, 2, NULL);
        """)
        add(c, 'v2', 1, '2025-04-01')
        add(c, 'v2', 2, '2025-04-01', species=3)
        add(c, 'v2', 3, '2025-04-02', species=4)
    rows = read_database(path, tz='UTC')
    assert rows[1].scientific_name == 'Species alpha'
    assert rows[1].common_name == 'Synthetic bird'
    assert rows[2].scientific_name == 'power_tool'
    assert rows[2].common_name == ''
    # legacy_id is not the v2 identity: all three rows deliberately share it.
    assert aggregate(rows, [date(2025, 4, 1), date(2025, 4, 2)], 'Species alpha').daily == [2, 0]


@pytest.mark.parametrize('state', ['migrating', 'paused', 'failed', 'validating', 'cutover'])
@pytest.mark.parametrize('table', ['migration_states', 'migration_state'])
def test_incomplete_v2_migration_is_not_silently_charted(tmp_path, state, table):
    path = make_v2(tmp_path)
    with closing(sqlite3.connect(path)) as c, c:
        c.execute(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, state TEXT, related_data_error TEXT)')
        c.execute(f'INSERT INTO {table} VALUES (1, ?, NULL)', (state,))
    with pytest.raises(DatabaseError, match='migration is incomplete'):
        read_database(path)


def test_completed_v2_migration_with_failed_reviews_is_rejected(tmp_path):
    path = make_v2(tmp_path)
    with closing(sqlite3.connect(path)) as c, c:
        c.execute('CREATE TABLE migration_states (state TEXT, related_data_error TEXT)')
        c.execute("INSERT INTO migration_states VALUES ('completed', 'Review migration failed')")
    with pytest.raises(DatabaseError, match='migration is incomplete'):
        read_database(path)


@pytest.mark.parametrize('state', ['idle', 'completed'])
def test_fresh_or_completed_v2_database_is_readable(tmp_path, state):
    path = make_v2(tmp_path)
    with closing(sqlite3.connect(path)) as c, c:
        c.execute('CREATE TABLE migration_states (state TEXT)')
        c.execute('INSERT INTO migration_states VALUES (?)', (state,))
    assert read_database(path) == []


def test_missing_directory_invalid_empty_and_ambiguous_files(tmp_path):
    missing = tmp_path / 'missing.db'
    with pytest.raises(FileNotFoundError):
        read_database(missing)
    assert not missing.exists()
    with pytest.raises(IsADirectoryError):
        read_database(tmp_path)
    invalid = tmp_path / 'invalid.db'
    invalid.write_text('not SQLite')
    with pytest.raises(DatabaseError, match='Cannot read SQLite'):
        read_database(invalid)
    invalid.write_bytes(b'')
    with pytest.raises(DatabaseError, match='Unrecognised'):
        read_database(invalid)
    with closing(sqlite3.connect(invalid)) as c:
        c.executescript(LEGACY + V2)
    with pytest.raises(DatabaseError, match='Ambiguous'):
        read_database(invalid)


def test_incomplete_review_schema_is_rejected(station):
    path, schema = station
    table = 'note_reviews' if schema == 'legacy' else 'detection_reviews'
    with closing(sqlite3.connect(path)) as c, c:
        c.execute(f'DROP TABLE {table}')
        c.execute(f'CREATE TABLE {table} (id INTEGER)')
    with pytest.raises(DatabaseError, match='missing columns'):
        read_database(path)


@pytest.mark.parametrize('score', [-.01, 1.01, float('nan'), float('inf')])
def test_bad_confidence_option(station, score):
    with pytest.raises(ValueError, match='min_confidence'):
        read_database(station[0], min_confidence=score)


@pytest.mark.parametrize('value', ['bad', -1, 2])
def test_bad_detection_confidence(station, value):
    path, schema = station
    populate(path, schema)
    with closing(sqlite3.connect(path)) as c, c:
        table = 'notes' if schema == 'legacy' else 'detections'
        c.execute(f'UPDATE {table} SET confidence = ? WHERE id = 3', (value,))
    with pytest.raises(DatabaseError, match='Invalid .* detection 3'):
        read_database(path)


@pytest.mark.parametrize('column,value', [('label_id', 999), ('detected_at', 'yesterday'),
                                        ('detected_at', 1750000000000)])
def test_bad_v2_reference_or_timestamp(tmp_path, column, value):
    path = make_v2(tmp_path)
    with closing(sqlite3.connect(path)) as c, c:
        add(c, 'v2', 1, '2025-04-01')
        c.execute(f'UPDATE detections SET {column} = ? WHERE id = 1', (value,))
    with pytest.raises(DatabaseError, match='Invalid v2 detection 1'):
        read_database(path)


def test_bad_legacy_date_is_reported(tmp_path):
    path = tmp_path / 'legacy.db'
    with closing(sqlite3.connect(path)) as c, c:
        c.executescript(LEGACY)
        add(c, 'legacy', 1, 'not a date')
    with pytest.raises(DatabaseError, match='Invalid legacy detection 1'):
        read_database(path)
