"""Create a private, runnable course package; never commit its licensed data.

Project authors: Yingni Chang and Yikai Shen.

Run from Final: python package_submission.py
The package includes normalized data and the seven raw parquet inputs, so the
grader can rebuild both the data pipeline and all research without WRDS login.
"""
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    tracked = subprocess.run(['git', 'ls-files', '--', '.'], cwd=ROOT,
                             check=True, capture_output=True, text=True).stdout.splitlines()
    selected = {ROOT / p for p in tracked if not p.endswith('.pptx')
                and Path(p).name not in {'critique.md', 'PAPER_ALIGNMENT_REVIEW.md', '.gitattributes', '.gitignore'}}
    selected.update(ROOT / p for p in [
        'crsp_pipeline/import_web.py', 'tests/test_import_web.py',
        'presentation/build_pdf.py', 'presentation/render_previews.mjs',
        'presentation/numeric_views.py', 'presentation/conservative_formula.pptx',
        'research/studies/feedback_costs.py','research/studies/uk_comparison.py','research/feedback_summary.py',
        'tests/test_feedback.py','data/uk_source.json','submission_runner.py','tests/test_submission_runner.py',
        'presentation/professor_questions.py',
        'presentation/build_speech_notes.py', 'presentation/speech_notes.py',
        'presentation/speaker_notes.md', 'output/pdf/conservative_formula_speech_notes.pdf',
        'presentation/build_short_speech_notes.py', 'presentation/speaker_notes_short.md',
        'output/pdf/conservative_formula_short_speech_notes.pdf',
        'presentation/conservative_formula.pdf', 'build_report_pdf.py',
        'output/pdf/conservative_formula_report.pdf', 'package_submission.py'])
    selected.update(ROOT / 'data' / p for p in [
        'crsp_monthly_normalized.parquet', 'benchmark_monthly.csv', 'ff_factors_monthly.csv',
        'audit/worked_examples.csv'])
    selected.update((ROOT / 'data/raw').glob('*.parquet'))
    selected.add(ROOT / 'data/raw/extract_log.json')
    selected.add(ROOT / 'data/raw/uk/compustat_global_uk_2013_2024.zip')
    selected.add(ROOT / 'data/raw/uk/query.sql')
    selected.add(ROOT / 'data/raw/wrds_complete/crsp_monthly_legacy_1925_2024.zip')
    selected.update((ROOT / 'results/feedback_costs').glob('*'))
    selected.update((ROOT / 'results/uk_comparison').glob('*'))
    # Source receipts contain metadata, not security observations.
    selected.add(ROOT / 'data/raw/wrds_complete/download_manifest.json')
    selected = {p for p in selected if p.is_file()}
    required = [ROOT / 'conservative_formula_final.ipynb',
                ROOT / 'presentation/conservative_formula.pdf',
                ROOT / 'output/pdf/conservative_formula_report.pdf',
                ROOT / 'output/pdf/conservative_formula_speech_notes.pdf',
                ROOT / 'data/crsp_monthly_normalized.parquet']
    if not all(p in selected for p in required):
        raise FileNotFoundError('Execute the notebook and build the report, slide and speech-note PDFs and normalized data first')
    output = ROOT / 'output/submission/MTH9897_Conservative_Formula_Final.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        for p in sorted(selected): z.write(p, 'Final/' + p.relative_to(ROOT).as_posix())
        z.writestr('PRIVATE_DATA_NOTICE.txt',
                   'Project authors: Yingni Chang and Yikai Shen.\n'
                   'Contains licensed CRSP and Compustat Global security data. Submit only through the authorized course channel.\n'
                   'Do not upload this archive to a public GitHub repository.\n'
                   'Run from Final: pip install -r requirements.txt; python -m crsp_pipeline build;\n'
                   'python -m research.run_all; python build_notebook.py; python execute_notebook.py;\n'
                   'python build_report_pdf.py; python presentation/build_pdf.py; '
                   'python presentation/build_speech_notes.py; '
                   'python presentation/build_short_speech_notes.py. '
                   'The executed notebook also opens using cached results.\n')
    with zipfile.ZipFile(output) as z:
        bad = z.testzip()
        if bad: raise ValueError(f'Corrupt archive member: {bad}')
    print(f'Created {output}: {len(selected)} files, {output.stat().st_size / 1024**2:.1f} MiB')


if __name__ == '__main__': main()
