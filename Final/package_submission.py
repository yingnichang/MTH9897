"""Build the minimal private submission. Authors: Yingni Chang and Yikai Shen.

Notebook, analysis/runtime code, complete data, cached results and final report/slide PDFs.
Document generators, speech notes and presentation source stay in GitHub for audit.
"""
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
ARCHIVE=ROOT/'output/submission/MTH9897_Conservative_Formula_Final.zip'


def submission_files(root=ROOT):
    """Explicit archive map; independent of Git and excludes document-generation tools."""
    root=Path(root)
    files={}
    def add(relative, destination=None):
        source=root/relative
        if not source.is_file():raise FileNotFoundError(f'Required submission file missing: {source}')
        files['Final/'+(destination or relative)]=source
    for name in ['conservative_formula_final.ipynb','submission_runner.py','execute_notebook.py',
                 'requirements.txt','requirements-lock.txt','data/manifest.json','data/uk_source.json']:
        add(name)
    for folder in ['research','crsp_pipeline']:
        for path in sorted((root/folder).rglob('*.py')):add(path.relative_to(root).as_posix())
    for path in sorted((root/'research/studies/data').rglob('*')):
        if path.is_file():add(path.relative_to(root).as_posix())
    manifest=json.loads((root/'data/manifest.json').read_text(encoding='utf-8'))
    for category in ['raw_inputs','outputs','audits']:
        for name in manifest[category]:add('data/'+name)
    for name in ['data/audit/worked_examples.csv','data/raw/extract_log.json',
                 'data/raw/wrds_complete/download_manifest.json',
                 'data/raw/wrds_complete/crsp_monthly_legacy_1925_2024.zip',
                 'data/raw/uk/compustat_global_uk_2013_2024.zip','data/raw/uk/query.sql']:
        add(name)
    add('results/manifest.json')
    result_manifest=json.loads((root/'results/manifest.json').read_text(encoding='utf-8'))
    for name in result_manifest['files']:add('results/'+name)
    add('presentation/conservative_formula.pdf','conservative_formula_presentation.pdf')
    add('output/pdf/conservative_formula_report.pdf','conservative_formula_report.pdf')
    return files


README='''Conservative Formula - Final Submission
Authors: Yingni Chang and Yikai Shen
MTH 9897, Project 8

MAIN REPORT: conservative_formula_final.ipynb
COMPANION WRITTEN REPORT: conservative_formula_report.pdf
FINAL PRESENTATION: conservative_formula_presentation.pdf (21 slides)

Keep this Final folder intact. Install Python 3.12 and run:
    python -m pip install -r requirements.txt
    python -m jupyterlab
Open conservative_formula_final.ipynb, choose RUN_MODE near the top, then
Restart Kernel and Run All Cells. Save the notebook after running.

RUN_MODE="cached": verify saved results and display the complete report.
RUN_MODE="analysis": rerun all 14 studies using the supplied cleaned inputs.
RUN_MODE="full": rebuild the US inputs from raw data, rerun all studies,
and display their results. The UK and quote analyses read their supplied exports.
No WRDS login or internet data download is needed for these modes.
Cached mode takes seconds. A full research rebuild can take 16 minutes or longer.

Optional command-line rebuild:
    python submission_runner.py --mode full
    python execute_notebook.py

Folder contents:
    research/ and crsp_pipeline/ : calculation and data-cleaning code
    data/ : complete licensed inputs and audit records
    results/ : cached aggregate results, figures and provenance hashes

Speech notes, the presentation source folder, and scripts that generate the
notebook, report or slides are excluded from this submission. They remain at:
https://github.com/yingnichang/MTH9897/tree/main/Final
The included execute_notebook.py executes the existing final notebook.

This package contains licensed CRSP and Compustat Global observations.
Use the authorized private course submission channel; do not publish the data.
'''


def main():
    files=submission_files()
    ARCHIVE.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(ARCHIVE,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for name,source in sorted(files.items()):z.write(source,name)
        z.writestr('Final/README.txt',README)
        z.writestr('PRIVATE_DATA_NOTICE.txt','Authors: Yingni Chang and Yikai Shen.\nLicensed CRSP and Compustat Global data: private course submission only.\n')
    with zipfile.ZipFile(ARCHIVE) as z:
        if bad:=z.testzip():raise ValueError(f'Corrupt archive member: {bad}')
    print(f'Created {ARCHIVE}: {len(files)+2} members, {ARCHIVE.stat().st_size/1024**2:.1f} MiB')


if __name__=='__main__':main()
