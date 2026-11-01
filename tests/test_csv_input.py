from datetime import date

import pytest

from beakplot import aggregate, read_csv


def write_csv(tmp_path, text):
    path = tmp_path / 'synthetic.csv'
    path.write_text(text, encoding='utf-8')
    return path


def test_article_export_columns_bom_reviews_and_duplicate_ids(tmp_path):
    path = write_csv(tmp_path, '\ufeffmonitor_id,detection_id,date_local,time_local,scientific_name,review_status,confidence\n'
                     'a,1,2025-04-01,06:15:00,Species alpha,,.8\n'
                     'a,1,2025-04-01,06:15:00,Species alpha,false_positive,.8\n'
                     'a,2,2025-04-02,06:15:00,Species beta,,.8\n'
                     'a,3,2025-04-03,06:29:59,Species alpha,,.8\n'
                     'a,3,2025-04-03,06:29:59,Species alpha,,.8\n')
    rows = read_csv(path)
    assert [r.detection_id for r in rows] == ['2', '3']
    counts = aggregate(rows, [date(2025, 4, i) for i in (1, 2, 3)], 'Species alpha')
    assert counts.daily == [None, 0, 1]
    assert counts.quarter_hours[2][25] == 1


def test_minimal_csv_without_ids_counts_independent_rows(tmp_path):
    path = write_csv(tmp_path, 'date,time,scientific_name\n'
                     '2025-04-01,06:15,Species alpha\n2025-04-01,06:15,Species alpha\n')
    rows = read_csv(path)
    assert len(rows) == 2
    assert rows[0].monitor_id == str(path)
    assert rows[0].confidence is None


def test_custom_headers_names_and_inclusive_confidence(tmp_path):
    path = write_csv(tmp_path, 'day,clock,taxon,name,score\n'
                     '2025-04-01,06:15,Species alpha,Synthetic bird,.79\n'
                     '2025-04-02,06:15,Species alpha,Synthetic bird,.8\n')
    rows = read_csv(path, columns={'date': 'day', 'time': 'clock', 'scientific_name': 'taxon',
                                  'common_name': 'name', 'confidence': 'score'}, min_confidence=.8)
    assert len(rows) == 1
    assert rows[0].date == date(2025, 4, 2)
    assert rows[0].common_name == 'Synthetic bird'


@pytest.mark.parametrize('text,message', [
    ('', 'header row'),
    ('"unterminated', 'CSV header'),
    ('date,date,scientific_name\n', 'unique'),
    ('date,time\n', 'scientific_name'),
    ('date,time,scientific_name\n2025-04-01,06:00,\n', 'line 2'),
    ('date,time,scientific_name\n2025-04-01,06:00,Species alpha,extra\n', 'line 2'),
    ('date,time,scientific_name\nbad,06:00,Species alpha\n', 'line 2'),
    ('date,time,scientific_name\n2025-04-01,06:00+01:00,Species alpha\n', 'without an offset'),
    ('date,time,scientific_name,confidence\n2025-04-01,06:00,Species alpha,nan\n', 'confidence'),
    ('date,time,scientific_name\n"unterminated', 'line 2'),
])
def test_invalid_csv_has_clear_error(tmp_path, text, message):
    with pytest.raises(ValueError, match=message):
        read_csv(write_csv(tmp_path, text))


def test_confidence_filter_requires_scores_and_explicit_headers_must_exist(tmp_path):
    path = write_csv(tmp_path, 'date,time,scientific_name\n2025-04-01,06:00,Species alpha\n')
    with pytest.raises(ValueError, match='confidence'):
        read_csv(path, min_confidence=.5)
    with pytest.raises(ValueError, match='common_name'):
        read_csv(path, columns={'common_name': 'missing'})
    path.write_text('date,time,scientific_name,confidence\n2025-04-01,06:00,Species alpha,\n')
    with pytest.raises(ValueError, match='line 2'):
        read_csv(path, min_confidence=.5)
