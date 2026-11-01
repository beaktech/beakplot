"""CLI checks using synthetic files only, including real subprocess rendering."""

from contextlib import closing
from datetime import date
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from beakplot import cli
from test_database import LEGACY, V2, add


@pytest.fixture(params=['legacy', 'v2'])
def input_db(request, tmp_path):
    schema = request.param
    path = tmp_path / f'{schema}.db'
    with closing(sqlite3.connect(path)) as c, c:
        c.executescript(LEGACY if schema == 'legacy' else V2)
        add(c, schema, 1, '2025-04-01', review='false_positive')
        add(c, schema, 2, '2025-04-02', species=2)
        add(c, schema, 3, '2025-04-03')
        add(c, schema, 4, '2025-04-05', confidence=.4)
        if schema == 'legacy':
            c.execute("UPDATE notes SET common_name = 'Synthetic alpha' WHERE scientific_name = 'Species alpha'")
    return path


def command(input_db, tmp_path, kind='daily'):
    args = [kind, '--db', str(input_db), '--species', 'Species alpha', '--tz', 'UTC',
            '--out', str(tmp_path / 'chart.svg')]
    if kind == 'heatmap':
        args += ['--lat', '50', '--lon', '0']
    return args


def capture_plot(monkeypatch):
    captured = {}
    def daily(series, dates, **options):
        captured.update(series=series, dates=dates, options=options)
        return object()
    monkeypatch.setattr(cli, 'daily_counts', daily)
    monkeypatch.setattr(cli, '_save', lambda *args: None)
    return captured


def test_default_range_uses_all_retained_species_and_includes_gaps(input_db, tmp_path, monkeypatch):
    captured = capture_plot(monkeypatch)
    assert cli.main(command(input_db, tmp_path)) == 0
    assert captured['dates'] == [date(2025, 4, i) for i in range(2, 6)]
    assert list(captured['series'].values()) == [[0, 1, None, 1]]
    assert 'automatic identifications' in captured['options']['subtitle']
    expected_name = 'Synthetic alpha' if input_db.stem == 'legacy' else 'Species alpha'
    assert captured['options']['title'].startswith(expected_name)


@pytest.mark.parametrize('flags,expected', [
    (['--from', '2025-04-03'], [3, 4, 5]),
    (['--to', '2025-04-03'], [2, 3]),
    (['--from', '2025-04-01', '--to', '2025-04-06'], [1, 2, 3, 4, 5, 6]),
    (['--min-confidence', '.8'], [2, 3]),
])
def test_partial_and_explicit_date_bounds(input_db, tmp_path, monkeypatch, flags, expected):
    captured = capture_plot(monkeypatch)
    assert cli.main(command(input_db, tmp_path) + flags) == 0
    assert [d.day for d in captured['dates']] == expected


def test_known_species_with_zero_in_selected_range_is_valid(input_db, tmp_path, monkeypatch):
    captured = capture_plot(monkeypatch)
    assert cli.main(command(input_db, tmp_path) + ['--from', '2025-04-02', '--to', '2025-04-02']) == 0
    assert list(captured['series'].values()) == [[0]]


def test_multiple_stations_use_union_dates_and_keep_empty_panel(input_db, tmp_path, monkeypatch):
    other = tmp_path / 'second.db'
    with closing(sqlite3.connect(other)) as c, c:
        c.executescript(LEGACY)
        add(c, 'legacy', 1, '2025-04-07', species=2)
    captured = capture_plot(monkeypatch)
    args = command(input_db, tmp_path) + ['--db', str(other), '--label', 'First', '--label', 'Second']
    assert cli.main(args) == 0
    assert captured['dates'][0] == date(2025, 4, 2)
    assert captured['dates'][-1] == date(2025, 4, 7)
    assert captured['series']['Second'] == [None, None, None, None, None, 0]
    assert cli.main(args + ['--to', '2025-04-03']) == 0
    assert captured['series']['Second'] == [None, None]


def test_species_counts_names_and_filters(input_db, capsys):
    assert cli.main(['species', '--db', str(input_db), '--tz', 'UTC']) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == 'Scientific name\tCommon name\tDetections'
    assert lines[1].split('\t')[::2] == ['Species alpha', '2']
    assert lines[2].split('\t')[::2] == ['Species beta', '1']
    assert cli.main(['species', '--db', str(input_db), '--tz', 'UTC', '--min-confidence', '.8',
                     '--from', '2025-04-03', '--to', '2025-04-03']) == 0
    assert capsys.readouterr().out.splitlines()[1].endswith('\t1')


def test_unknown_species_suggests_close_matches(input_db, tmp_path, capsys):
    args = command(input_db, tmp_path)
    args[args.index('--species') + 1] = 'Species alpa'
    assert cli.main(args) == 2
    error = capsys.readouterr().err
    assert 'Unknown species' in error and 'Did you mean' in error and 'Species alpha' in error
    assert not (tmp_path / 'chart.svg').exists()


@pytest.mark.parametrize('flags,message', [
    (['--from', '2025-04-04', '--to', '2025-04-04'], 'Empty date range'),
    (['--from', '2025-04-10'], 'Empty date range'),
    (['--to', '2025-03-01'], 'Empty date range'),
    (['--from', '2025-04-05', '--to', '2025-04-02'], '--from must be on or before --to'),
    (['--min-confidence', '1'], 'No retained detections'),
    (['--label', 'One', '--label', 'Two'], 'one --label per input'),
    (['--date-column', 'day'], 'require --csv'),
])
def test_clear_errors_leave_existing_output_untouched(input_db, tmp_path, capsys, flags, message):
    output = tmp_path / 'chart.svg'
    output.write_text('existing chart')
    assert cli.main(command(input_db, tmp_path) + flags) == 2
    assert message in capsys.readouterr().err
    assert output.read_text() == 'existing chart'


def test_wrong_path_and_bad_output(input_db, tmp_path, capsys):
    args = command(tmp_path / 'missing.db', tmp_path)
    assert cli.main(args) == 2
    assert 'missing.db' in capsys.readouterr().err
    assert not (tmp_path / 'missing.db').exists()
    for output in (tmp_path / 'chart.pdf', tmp_path / 'absent' / 'chart.svg'):
        assert cli.main(command(input_db, tmp_path) + ['--out', str(output)]) == 2
        assert 'Output' in capsys.readouterr().err


def test_repeated_inputs_labels_and_multiple_heatmap_sources(input_db, tmp_path, capsys):
    assert cli.main(command(input_db, tmp_path) + ['--db', str(input_db)]) == 2
    assert 'more than once' in capsys.readouterr().err
    assert cli.main(command(input_db, tmp_path, 'heatmap') + ['--db', str(input_db)]) == 2
    assert 'exactly one input' in capsys.readouterr().err
    other = tmp_path / 'copy.db'
    other.write_bytes(input_db.read_bytes())
    assert cli.main(command(input_db, tmp_path) + ['--db', str(other), '--label', 'Same', '--label', 'Same']) == 2
    assert 'unique' in capsys.readouterr().err


@pytest.mark.parametrize('flag,value', [('--from', 'yesterday'), ('--tz', 'Invalid/Zone'),
                                       ('--min-confidence', 'nan'), ('--min-confidence', '1.1'),
                                       ('--lat', '91'), ('--lon', 'inf'), ('--vmax', '0')])
def test_invalid_options_are_argparse_errors(input_db, tmp_path, flag, value):
    with pytest.raises(SystemExit) as error:
        cli.main(command(input_db, tmp_path, 'heatmap') + [flag, value])
    assert error.value.code == 2


@pytest.mark.parametrize('kind,extension', [('daily', 'svg'), ('heatmap', 'svg'), ('heatmap', 'png')])
def test_module_command_renders_real_files(input_db, tmp_path, kind, extension):
    output = tmp_path / f'output.{extension}'
    args = command(input_db, tmp_path, kind) + ['--out', str(output), '--title', 'Synthetic chart',
                                               '--subtitle', 'Synthetic subtitle']
    if kind == 'heatmap':
        args += ['--vmax', '10']
    result = subprocess.run([sys.executable, '-m', 'beakplot', *args], capture_output=True, text=True,
                            env={**os.environ, 'MPLBACKEND': 'Agg'}, timeout=30)
    assert result.returncode == 0, result.stderr
    assert '2025-04-02 to 2025-04-05' in result.stdout
    if extension == 'svg':
        root = ET.parse(output).getroot()
        texts = ''.join(root.itertext())
        assert 'Synthetic chart' in texts and 'Synthetic subtitle' in texts
        assert root.tag.endswith('svg')
    else:
        assert output.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')


def test_failed_render_preserves_output_and_cleans_temporary_file(tmp_path):
    output = tmp_path / 'chart.svg'
    output.write_text('previous')
    import matplotlib.pyplot as plt
    fig = plt.figure()
    def fail(*args, **kwargs):
        raise OSError('synthetic disk failure')
    fig.savefig = fail
    with pytest.raises(OSError, match='synthetic disk failure'):
        cli._save(fig, output)
    assert output.read_text() == 'previous'
    assert list(tmp_path.iterdir()) == [output]
    assert not plt.fignum_exists(fig.number)


def test_output_cannot_replace_input_even_through_hard_link(input_db, tmp_path, capsys):
    output = tmp_path / 'database.svg'
    os.link(input_db, output)
    before = input_db.read_bytes()
    assert cli.main(command(input_db, tmp_path) + ['--out', str(output)]) == 2
    assert 'overwrite an input' in capsys.readouterr().err
    assert input_db.read_bytes() == before


def test_csv_cli_custom_columns_and_common_name_matching(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'input.csv'
    path.write_text('day,clock,taxon,name,id,verified\n'
                    '2025-04-01,06:15,Species alpha,Synthetic alpha,1,\n'
                    '2025-04-01,06:15,Species alpha,Synthetic alpha,1,\n'
                    '2025-04-02,06:15,Species beta,Synthetic beta,2,false_positive\n')
    shared = ['--csv', str(path), '--date-column', 'day', '--time-column', 'clock',
              '--species-column', 'taxon', '--common-name-column', 'name']
    assert cli.main(['species', *shared]) == 0
    assert capsys.readouterr().out.splitlines()[1] == 'Species alpha\tSynthetic alpha\t1'
    captured = capture_plot(monkeypatch)
    assert cli.main(['daily', *shared, '--species', 'synthetic alpha', '--out', str(tmp_path / 'chart.svg')]) == 0
    assert captured['dates'] == [date(2025, 4, 1)]
    assert list(captured['series'].values()) == [[1]]


def test_heatmap_help_explains_coordinates_and_defaults(capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(['heatmap', '--help'])
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    assert 'used only for sunrise and sunset' in help_text
    assert 'first retained date' in help_text and 'last retained date' in help_text


def test_species_ambiguity_and_no_close_match(tmp_path, capsys):
    path = tmp_path / 'names.csv'
    path.write_text('date,time,scientific_name,common_name\n'
                    '2025-04-01,06:00,Species alpha,Synthetic bird\n'
                    '2025-04-01,06:00,Species beta,Synthetic bird\n')
    args = ['daily', '--csv', str(path), '--out', str(tmp_path / 'chart.svg'), '--species']
    assert cli.main(args + ['Synthetic bird']) == 2
    assert 'Ambiguous species' in capsys.readouterr().err
    assert cli.main(args + ['zzzzzzzzz']) == 2
    error = capsys.readouterr().err
    assert 'Unknown species' in error and 'beakplot species' in error


def test_csv_multi_monitor_file_is_rejected(tmp_path, capsys):
    path = tmp_path / 'monitors.csv'
    path.write_text('date,time,scientific_name,monitor_id\n'
                    '2025-04-01,06:00,Species alpha,a\n'
                    '2025-04-01,06:00,Species alpha,b\n')
    assert cli.main(['species', '--csv', str(path)]) == 2
    assert 'multiple monitors' in capsys.readouterr().err


def test_module_errors_exit_two_without_traceback(tmp_path):
    result = subprocess.run([sys.executable, '-m', 'beakplot', 'species', '--db', str(tmp_path / 'missing.db')],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert 'missing.db' in result.stderr and 'Traceback' not in result.stderr


def test_cli_v2_local_date_defaults_and_october_clock_change(tmp_path):
    path = tmp_path / 'october.db'
    with closing(sqlite3.connect(path)) as c, c:
        c.executescript(V2)
        add(c, 'v2', 1, '2025-10-24', '23:45:00')
        add(c, 'v2', 2, '2025-10-26', '00:30:00')
        add(c, 'v2', 3, '2025-10-26', '01:30:00')
    output = tmp_path / 'clock-change.svg'
    assert cli.main(['heatmap', '--db', str(path), '--species', 'Species alpha', '--tz', 'Europe/London',
                     '--lat', '50', '--lon', '0', '--out', str(output)]) == 0
    text = ''.join(ET.parse(output).getroot().itertext())
    assert 'local clock time' in text


@pytest.mark.parametrize('option', ['--db', '--csv'])
def test_missing_input_has_friendly_exact_message(tmp_path, capsys, option):
    path = tmp_path / 'missing file'
    assert cli.main(['species', option, str(path)]) == 2
    assert capsys.readouterr().err.strip() == f'beakplot: error: Database not found: {path}'
