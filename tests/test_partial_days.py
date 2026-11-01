from datetime import date, datetime, timezone
import time
from zoneinfo import ZoneInfo

import pytest

from beakplot import cli
from test_cli import capture_plot


@pytest.fixture
def current_csv(tmp_path, monkeypatch):
    path = tmp_path / 'current.csv'
    path.write_text('date,time,scientific_name\n'
                    '2025-10-25,12:00,Erithacus rubecula\n'
                    '2025-10-26,01:30,Erithacus rubecula\n')
    monkeypatch.setattr(cli, '_today', lambda tz: date(2025, 10, 26))
    return path


@pytest.mark.parametrize('bounds', [[], ['--to', '2025-10-26'], ['--to', '2025-10-28']])
def test_today_excluded_even_with_explicit_end(current_csv, tmp_path, monkeypatch, capsys, bounds):
    captured = capture_plot(monkeypatch)
    args = ['daily', '--csv', str(current_csv), '--species', 'Robin', '--out', str(tmp_path / 'chart.svg')]
    assert cli.main(args + bounds) == 0
    assert captured['dates'] == [date(2025, 10, 25)]
    assert "Excluding today's partial day" in capsys.readouterr().err
    assert cli.main(args + ['--include-partial']) == 0
    assert captured['dates'] == [date(2025, 10, 25), date(2025, 10, 26)]


def test_species_listing_obeys_partial_option(current_csv, capsys):
    args = ['species', '--csv', str(current_csv)]
    assert cli.main(args) == 0
    assert capsys.readouterr().out.splitlines()[1].endswith('\t1')
    assert cli.main(args + ['--include-partial']) == 0
    assert capsys.readouterr().out.splitlines()[1].endswith('\t2')


def test_today_only_range_explains_opt_in(current_csv, tmp_path, capsys, monkeypatch):
    args = ['daily', '--csv', str(current_csv), '--species', 'Robin', '--from', '2025-10-26',
            '--out', str(tmp_path / 'chart.svg')]
    assert cli.main(args) == 2
    assert '--include-partial' in capsys.readouterr().err
    current_csv.write_text('date,time,scientific_name\n2025-10-26,01:00,Erithacus rubecula\n')
    assert cli.main(['species', '--csv', str(current_csv)]) == 2
    assert '--include-partial' in capsys.readouterr().err
    captured = capture_plot(monkeypatch)
    assert cli.main(args + ['--include-partial']) == 0
    assert captured['dates'] == [date(2025, 10, 26)]


def test_historical_edges_and_earlier_requested_range_stay(current_csv, tmp_path, monkeypatch):
    captured = capture_plot(monkeypatch)
    args = ['daily', '--csv', str(current_csv), '--species', 'Robin', '--out', str(tmp_path / 'chart.svg')]
    assert cli.main(args + ['--to', '2025-10-25']) == 0
    assert captured['dates'] == [date(2025, 10, 25)]
    monkeypatch.setattr(cli, '_today', lambda tz: date(2025, 10, 27))
    assert cli.main(args) == 0
    assert captured['dates'] == [date(2025, 10, 25), date(2025, 10, 26)]


def test_today_uses_selected_zone_across_midnight(tmp_path, monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2025, 10, 25, 23, 30, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(cli, 'datetime', FixedDateTime)
    assert cli._today(ZoneInfo('Europe/London')) == date(2025, 10, 26)
    assert cli._today(ZoneInfo('America/New_York')) == date(2025, 10, 25)
    path = tmp_path / 'date-boundary.csv'
    path.write_text('date,time,scientific_name\n2025-10-24,12:00,Erithacus rubecula\n'
                    '2025-10-25,12:00,Erithacus rubecula\n')
    captured = capture_plot(monkeypatch)
    args = ['daily', '--csv', str(path), '--species', 'Robin', '--out', str(tmp_path / 'chart.svg')]
    assert cli.main(args + ['--tz', 'America/New_York']) == 0
    assert captured['dates'][-1] == date(2025, 10, 24)
    assert cli.main(args + ['--tz', 'Europe/London']) == 0
    assert captured['dates'][-1] == date(2025, 10, 25)


@pytest.mark.skipif(not hasattr(time, 'tzset'), reason='tzset unavailable')
def test_today_defaults_to_system_zone(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2025, 10, 25, 23, 30, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(cli, 'datetime', FixedDateTime)
    with monkeypatch.context() as environment:
        environment.setenv('TZ', 'Pacific/Kiritimati')
        time.tzset()
        try:
            assert cli._today(None) == date(2025, 10, 26)
        finally:
            environment.undo()
            time.tzset()


def test_partial_help(capsys):
    with pytest.raises(SystemExit):
        cli.main(['daily', '--help'])
    help_text = capsys.readouterr().out
    assert '--include-partial' in help_text and 'today is otherwise excluded' in help_text
