import zipfile
import pandas as pd
import pytest

from crsp_pipeline.import_web import read_export


def test_names_export_maps_start_date_and_preserves_identifiers(tmp_path):
    path = tmp_path / 'names.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('names.csv', 'PERMNO,DATE,NAMEENDT,TICKER,SHRCD\n10000,1925-12-31,1926-12-31,ABC,10\n')
    frame = read_export(path, ['permno', 'namedt', 'nameendt', 'ticker', 'shrcd'], {'date': 'namedt'})
    assert frame.namedt.iloc[0] == pd.Timestamp('1925-12-31')
    assert frame.permno.iloc[0] == 10000
    assert frame.ticker.iloc[0] == 'ABC'


def test_crsp_return_missing_codes_are_not_zero(tmp_path):
    path = tmp_path / 'returns.csv'
    path.write_text('PERMNO,date,RET\n10000,1926-01-30,B\n10000,1926-02-26,-0.2\n')
    frame = read_export(path, ['permno', 'date', 'ret'])
    assert pd.isna(frame.ret.iloc[0])
    assert frame.ret.iloc[1] == -0.2


def test_missing_required_field_fails(tmp_path):
    path = tmp_path / 'returns.csv'
    path.write_text('PERMNO,date\n10000,1926-01-30\n')
    with pytest.raises(ValueError, match='missing'):
        read_export(path, ['permno', 'date', 'ret'])
