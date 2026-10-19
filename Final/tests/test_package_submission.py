"""Private submission scope and completeness. Authors: Yingni Chang and Yikai Shen."""
import json
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from package_submission import submission_files


@pytest.mark.skipif(not (ROOT/'data/raw/uk/compustat_global_uk_2013_2024.zip').exists(),reason='Private inputs not available')
def test_submission_has_runtime_data_and_final_presentation_only():
    files=submission_files()
    assert 'Final/conservative_formula_final.ipynb' in files
    assert 'Final/conservative_formula_presentation.pdf' in files
    assert files['Final/conservative_formula_presentation.pdf']==ROOT/'presentation/conservative_formula.pdf'
    assert not any(p.startswith('Final/presentation/') or p.startswith('Final/tests/') for p in files)
    assert not any('speech_notes' in p or 'speaker_notes' in p for p in files)
    for name in ['build_notebook.py','build_report_pdf.py','package_submission.py']:
        assert 'Final/'+name not in files
    for name in ['submission_runner.py','execute_notebook.py','requirements.txt']:
        assert 'Final/'+name in files
    m=json.loads((ROOT/'results/manifest.json').read_text())
    assert all('Final/'+name in files for name in m['last_run']['source_sha256'])
    assert all('Final/results/'+name in files for name in m['files'])
    m=json.loads((ROOT/'data/manifest.json').read_text())
    for category in ['raw_inputs','outputs','audits']:
        assert all('Final/data/'+name in files for name in m[category])
