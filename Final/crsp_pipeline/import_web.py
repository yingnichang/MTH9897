"""Import the full legacy WRDS web exports, then use the existing offline build.

Run from Final: python -m crsp_pipeline.import_web
The original downloads remain untouched in data/raw/wrds_complete.
"""
import datetime as dt
import json
import zipfile
from pathlib import Path

import pandas as pd

from . import config
from .extract import TABLES
from .provenance import sha256

FILES = {
    'msf': 'crsp_monthly_legacy_1925_2024.zip',
    'msenames': 'crsp_names_legacy.zip',
    'msedelist': 'crsp_delisting_legacy.zip',
    'msedist': 'crsp_distributions_legacy.zip',
    'msi': 'crsp_market_indexes_monthly_legacy.csv',
    'ff_factors': 'ff3_momentum_monthly.csv',
    'ff5_factors': 'ff5_momentum_monthly.csv',
}


def read_export(path, columns, rename=None):
    rename = rename or {}
    z = zipfile.ZipFile(path) if path.suffix == '.zip' else None
    source = z.open(z.namelist()[0]) if z else path.open('rb')
    with source:
        chunks = []
        for df in pd.read_csv(source, usecols=lambda c: rename.get(c.lower(), c.lower()) in columns,
                              chunksize=250000, low_memory=False):
            df.columns = [rename.get(c.lower(), c.lower()) for c in df.columns]
            chunks.append(df)
        out = pd.concat(chunks, ignore_index=True)
    if z: z.close()
    missing = set(columns) - set(out.columns)
    if missing: raise ValueError(f'{path.name}: missing {missing}')
    for col in columns:
        if col in {'ticker', 'comnam', 'shrcls'}:
            out[col] = out[col].astype('string')
        elif col in {'date', 'dateff', 'namedt', 'nameendt', 'dlstdt', 'dclrdt', 'exdt', 'rcrddt', 'paydt'}:
            out[col] = pd.to_datetime(out[col], errors='raise')
        else:
            out[col] = pd.to_numeric(out[col], errors='coerce')
    return out[columns]


def main():
    folder = config.RAW / 'wrds_complete'
    audit = json.loads((folder / 'download_manifest.json').read_text())
    log = {'extracted_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'host': 'wrds-www.wharton.upenn.edu', 'library': 'CRSP legacy annual / FF web exports',
           'start': config.EXTRACT_START, 'end': config.EXTRACT_END, 'tables': {}}
    # Match the SQL extract's ever-common-stock security universe.
    names = read_export(folder / FILES['msenames'], TABLES['msenames'][2], {'date': 'namedt'})
    common = set(names.loc[names.shrcd.isin(config.COMMON_SHARE_CODES), 'permno'])
    for table, filename in FILES.items():
        path = folder / filename
        if sha256(path) != audit['files'][filename]['sha256']:
            raise ValueError(f'Download hash mismatch: {filename}')
        df = names.copy() if table == 'msenames' else read_export(path, TABLES[table][2])
        before = len(df)
        if 'permno' in df:
            df = df.loc[df.permno.isin(common)].copy()
            df['permno'] = df.permno.astype('int64')
        if table == 'msedist': df = df.dropna(subset=['exdt', 'distcd'])
        if table == 'msedelist': df = df.dropna(subset=['dlstdt', 'dlstcd'])
        duplicate_rows = int(df.duplicated().sum())
        df = df.drop_duplicates().reset_index(drop=True)
        if table == 'msf' and df.duplicated(['permno', 'date']).any():
            raise ValueError('Conflicting monthly rows: inspect the WRDS join before proceeding')
        target = config.RAW / f'{table}.parquet'
        df.to_parquet(target, index=False, compression='zstd')
        log['tables'][table] = {'rows': len(df), 'source_rows': before,
            'exact_duplicate_rows_removed': duplicate_rows, 'file': target.name,
            'sha256': sha256(target), 'source_file': filename,
            'source_sha256': audit['files'][filename]['sha256'],
            'query_url': audit['files'][filename]['url']}
        print(f'{table}: {len(df):,} rows ({duplicate_rows:,} exact duplicates removed)', flush=True)
    log['msf_max_date'] = config.EXTRACT_END
    (config.RAW / 'extract_log.json').write_text(json.dumps(log, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
