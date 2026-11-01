from contextlib import closing
from datetime import date, time
import sqlite3

import pytest

from dayclock import Detection, common_name
from dayclock import cli
from dayclock.names import preferred_names
from test_database import V2, add
from test_cli import capture_plot


def test_bundled_names_recorded_priority_and_unknown_species():
    assert common_name('Erithacus rubecula') == 'European Robin'
    assert common_name('ARDEA CINEREA') == 'Grey Heron'
    assert common_name('Erithacus rubecula', 'Robin from station') == 'Robin from station'
    assert common_name('Unknown taxon') == 'Unknown taxon'
    rows = [Detection(date(2025, 1, 1), time(6), 'Erithacus rubecula') for _ in range(5)]
    rows.append(Detection(date(2025, 1, 2), time(6), 'Erithacus rubecula', common_name='Station Robin'))
    assert preferred_names(rows) == {'Erithacus rubecula': 'Station Robin'}


@pytest.fixture
def robin_db(tmp_path):
    path = tmp_path / 'robin.db'
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript(V2)
        connection.execute("UPDATE labels SET scientific_name = 'Erithacus rubecula' WHERE id = 1")
        add(connection, 'v2', 1, '2025-04-01')
        add(connection, 'v2', 2, '2025-04-02')
    return path


@pytest.mark.parametrize('query', ['Robin', 'rObIn', 'european robin', 'ERITHACUS RUBECULA'])
def test_v2_cli_uses_bundled_names_for_matching_and_titles(robin_db, tmp_path, monkeypatch, query):
    captured = capture_plot(monkeypatch)
    assert cli.main(['daily', '--db', str(robin_db), '--species', query,
                     '--out', str(tmp_path / 'robin.svg')]) == 0
    assert captured['options']['title'] == 'European Robin: daily detections'
    assert list(captured['series'].values()) == [[1, 1]]


def test_v2_species_list_and_close_match(robin_db, tmp_path, capsys):
    assert cli.main(['species', '--db', str(robin_db)]) == 0
    assert 'Erithacus rubecula\tEuropean Robin\t2' in capsys.readouterr().out
    assert cli.main(['daily', '--db', str(robin_db), '--species', 'Robni',
                     '--out', str(tmp_path / 'robin.svg')]) == 2
    error = capsys.readouterr().err
    assert 'Did you mean' in error and 'European Robin' in error and 'Erithacus rubecula' in error


def test_recorded_common_name_has_priority_in_cli(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'recorded.csv'
    path.write_text('date,time,scientific_name,common_name\n'
                    '2025-04-01,06:00,Erithacus rubecula,Station Robin\n'
                    '2025-04-02,06:00,Erithacus rubecula,\n')
    assert cli.main(['species', '--csv', str(path)]) == 0
    assert 'Erithacus rubecula\tStation Robin\t2' in capsys.readouterr().out
    captured = capture_plot(monkeypatch)
    assert cli.main(['daily', '--csv', str(path), '--species', 'station robin',
                     '--out', str(tmp_path / 'robin.svg')]) == 0
    assert captured['options']['title'] == 'Station Robin: daily detections'


def test_recorded_name_wins_over_conflicting_alias_and_lookup_is_not_a_species_source():
    rows = [Detection(date(2025, 4, 1), time(6), 'Erithacus rubecula'),
            Detection(date(2025, 4, 1), time(6), 'Synthetic species', common_name='Robin')]
    assert cli._species(rows, 'Robin') == 'Synthetic species'
    assert cli._species(rows, 'European Robin') == 'Erithacus rubecula'
    with pytest.raises(ValueError, match='Unknown species'):
        cli._species(rows, 'Grey Heron')
