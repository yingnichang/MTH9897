"""Submission notebook execution and offline packaging checks. Yingni Chang and Yikai Shen."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import submission_runner as runner


def saved_results(base):
    results=base/'results';results.mkdir()
    (results/'summary.csv').write_text('return\n0.1\n',encoding='utf-8')
    m=dict(last_run=dict(status='complete',source_sha256={}),studies={'study':{}},
           files={'summary.csv':{'sha256':hashlib.sha256((results/'summary.csv').read_bytes()).hexdigest()}},
           updated_utc='2026-10-18')
    (results/'manifest.json').write_text(json.dumps(m),encoding='utf-8')
    return results


def test_cached_report_runs_without_private_data_or_subprocess(tmp_path,monkeypatch):
    saved_results(tmp_path)
    monkeypatch.setattr(runner,'_run_step',lambda *a:pytest.fail('Cached mode must not run calculations'))
    record=runner.run_project('cached',tmp_path)
    assert record['completed_studies']==1 and record['verified_result_files']==1
    assert not record['analyses_recomputed'] and not record['data_rebuilt']


def test_changed_cached_results_are_rejected(tmp_path):
    result=saved_results(tmp_path);(result/'summary.csv').write_text('return\n9\n',encoding='utf-8')
    with pytest.raises(ValueError,match='Cached result missing or changed'):runner.run_project('cached',tmp_path)


def test_missing_data_stops_before_touching_results(tmp_path,monkeypatch):
    result=saved_results(tmp_path);before=(result/'manifest.json').read_bytes()
    monkeypatch.setattr(runner,'_run_step',lambda *a:pytest.fail('Must stop before executing a partial rebuild'))
    with pytest.raises(FileNotFoundError,match='complete course ZIP'):runner.run_project('full',tmp_path)
    assert (result/'manifest.json').read_bytes()==before


def test_full_run_executes_cleaning_then_all_studies(tmp_path,monkeypatch):
    saved_results(tmp_path)
    for name in runner.required_inputs('full'):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.touch()
    commands=[]
    monkeypatch.setattr(runner,'_run_step',lambda command,*args:commands.append(command))
    record=runner.run_project('full',tmp_path)
    assert commands[0][1:]==['-m','crsp_pipeline','build']
    assert commands[1][1:3]==['-m','research.run_all']
    assert record['data_rebuilt'] and record['analyses_recomputed']
    assert '--only' not in commands[1] # All studies, not a selected subset.


def test_subprocess_failure_prevents_second_stage(tmp_path,monkeypatch):
    for name in runner.required_inputs('full'):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.touch()
    calls=[]
    def failed(command,*args):
        calls.append(command);raise subprocess.CalledProcessError(1,command)
    monkeypatch.setattr(runner,'_run_step',failed)
    with pytest.raises(subprocess.CalledProcessError):runner.run_project('full',tmp_path)
    assert len(calls)==1


def test_analysis_plan_reuses_normalized_data_and_full_plan_rebuilds_it(tmp_path):
    assert len(runner.execution_plan('analysis',tmp_path))==1
    assert len(runner.execution_plan('full',tmp_path))==2
    assert 'data/crsp_monthly_normalized.parquet' in runner.required_inputs('analysis')
    assert 'data/crsp_monthly_normalized.parquet' not in runner.required_inputs('full')
    with pytest.raises(ValueError):runner.execution_plan('unknown',tmp_path)
