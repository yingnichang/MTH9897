"""Notebook execution controls. Authors: Yingni Chang and Yikai Shen.

Run from Final: python submission_runner.py --mode cached|analysis|full
No WRDS login or network connection is used. Private data accompany the course ZIP.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
RAW_TABLES = ('msf','msenames','msedelist','msedist','msi','ff_factors','ff5_factors')


def execution_plan(mode, result_root):
    if mode not in {'cached','analysis','full'}:
        raise ValueError('RUN_MODE must be cached, analysis or full')
    steps=[]
    if mode=='full':steps.append([sys.executable,'-m','crsp_pipeline','build'])
    if mode in {'analysis','full'}:
        steps.append([sys.executable,'-m','research.run_all','--results',str(Path(result_root).resolve())])
    return steps


def required_inputs(mode):
    if mode=='cached':return []
    files=[f'data/raw/{name}.parquet' for name in RAW_TABLES]
    files += ['data/raw/uk/compustat_global_uk_2013_2024.zip','data/uk_source.json',
              'data/raw/wrds_complete/crsp_monthly_legacy_1925_2024.zip',
              'data/raw/wrds_complete/download_manifest.json']
    if mode=='analysis':
        files += ['data/crsp_monthly_normalized.parquet','data/benchmark_monthly.csv',
                  'data/ff_factors_monthly.csv','data/manifest.json']
    return files


def _sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def verify_results(base, result_root):
    """Check saved outputs and their recorded scientific source bytes before display."""
    manifest=Path(result_root)/'manifest.json'
    if not manifest.is_file():
        raise FileNotFoundError('No results manifest. Extract the complete private course ZIP and choose RUN_MODE="full".')
    m=json.loads(manifest.read_text(encoding='utf-8'))
    if m.get('last_run',{}).get('status')!='complete':
        raise ValueError('The previous analysis did not finish. Choose analysis or full to rebuild it.')
    for name,record in m['files'].items():
        p=Path(result_root)/name
        if not p.is_file() or _sha(p)!=record['sha256']:
            raise ValueError(f'Cached result missing or changed: {name}. Choose analysis to recompute.')
    for name,digest in m['last_run'].get('source_sha256',{}).items():
        p=Path(base)/name
        if not p.is_file() or _sha(p)!=digest:
            raise ValueError(f'Scientific source changed: {name}. Choose analysis to recompute.')
    return m


def _run_step(command, base, log):
    """Stream progress into the notebook and an on-disk log, stopping on failure."""
    env=os.environ.copy();env['PYTHONIOENCODING']='utf-8'
    print('\nRunning: '+' '.join(command),flush=True)
    with log.open('a',encoding='utf-8') as saved:
        saved.write('\nCOMMAND: '+' '.join(command)+'\n')
        with subprocess.Popen(command,cwd=base,env=env,stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1) as process:
            for line in process.stdout:
                print(line,end='',flush=True);saved.write(line);saved.flush()
            status=process.wait()
    if status:raise subprocess.CalledProcessError(status,command)


def run_project(mode='cached', base=ROOT, result_root=None):
    base=Path(base).resolve()
    result_root=base/'results' if result_root is None else Path(result_root).resolve()
    steps=execution_plan(mode,result_root)
    missing=[name for name in required_inputs(mode) if not (base/name).is_file()]
    if missing:
        raise FileNotFoundError('Required private inputs are missing. Extract the complete course ZIP, keep its Final folder intact, and rerun.\n'+'\n'.join(missing))
    t0=time.monotonic()
    log=base/'output/execution/project_run.log'
    if steps:
        log.parent.mkdir(parents=True,exist_ok=True)
        for command in steps:_run_step(command,base,log)
    m=verify_results(base,result_root)
    record=dict(run_mode=mode,data_rebuilt=mode=='full',analyses_recomputed=mode!='cached',
                completed_studies=len(m['studies']),verified_result_files=len(m['files']),
                seconds=round(time.monotonic()-t0,2),results_last_updated_utc=m['updated_utc'])
    print('Cached results verified.' if mode=='cached' else 'Analysis completed. The following cells display the new results.',flush=True)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['cached','analysis','full'],default='cached')
    print(json.dumps(run_project(parser.parse_args().mode),indent=2))
