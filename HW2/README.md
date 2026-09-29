# MTH 9897 — Homework 2

Replication and extensions of Tables 1 and 4 in Bessembinder (2018),
*Do Stocks Outperform Treasury Bills?* The assignment is in `Instructions.md`.
Read `report/report.pdf` for the written results or `hw2_analysis.ipynb` for the
analysis, saved tables, and figures.

## Setup

Use Python 3.11 or newer. The regression checks were verified with Python 3.11.7,
NumPy 1.26.4, pandas 2.2.3, and Matplotlib 3.8.0. Run the commands below from this `HW2` directory.
Create an isolated environment and install the dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m ipykernel install --user --name mth9897-hw2 --display-name "MTH9897 HW2"
```

On macOS/Linux, activate with `source .venv/bin/activate` instead. The kernel
registration makes the environment available to Jupyter; select **MTH9897 HW2**
when opening the notebook interactively. A pre-existing Anaconda environment may
have older packages, so use the isolated environment or check the required versions.

The complete rebuild was validated with Python 3.11.7, NumPy 1.26.4, pandas 2.2.3,
Matplotlib 3.8.0, nbclient 0.8.0, and nbformat 5.9.2.

## Data and reproducibility checks

The three Ken French archives in `data/raw/` are pinned to the **August 2026 CRSP
release**, covering July 1926–August 2026. They are already included; no download is
needed. `data/vintage.json` records their source URLs, byte lengths, and SHA-256
checksums. The original download timestamp was not committed, so it is recorded as
`null`; each entry identifies the Git commit from which the manifest was reconstructed.

```powershell
python src/ff_data.py
python -m unittest discover -s tests -v
```

The tests verify the supplied archive checksums and all 24 snapshot audit facts,
reject a corrupted cache, check lagged portfolio decisions and missing-return
handling, and verify simulation units, exact moments, and chunk-independent draws.
They use small simulations and do not rerun the homework's full Monte Carlo work.

Keep the pinned archives when reproducing the reported results. The optional command
`python src/ff_data.py --refresh` replaces them with whatever is currently published
by Ken French. A new release may revise historical returns and will require reviewing
the snapshot checks in `src/ff_audit.py` and regenerating the results.

## Rebuild the analysis and report

1. Execute the notebook from a fresh kernel, from top to bottom. For a command-line
   run using the environment above:

   ```powershell
   python -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=mth9897-hw2 --ExecutePreprocessor.timeout=-1 hw2_analysis.ipynb
   ```

   Part 1 uses 250,000 paths and five seeds. Its validated CSV/JSON simulation caches
   are included in `output/`, so ordinary runs reuse them. A fully uncached run can
   take roughly half an hour or longer depending on the machine. Set the notebook's `REFRESH = True`
   only when deliberately recomputing the simulations, then restore it to `False`.
   This flag controls simulation caches; it does not refresh the raw data.
   Part 2 recomputes its 20,000 random industry paths from seed 0. CSV/JSON results in
   `output/` are included for reproducibility; intermediate plot PNGs are ignored.

2. Generate the LaTeX tables and vector figures from those outputs. The submitted
   tables and figures are also included, so the report can be compiled immediately:

   ```powershell
   python report/make_tables.py
   python report/make_figures.py
   ```

3. Compile the multi-file LaTeX report with a TeX distribution containing the packages
   listed in `report/report.tex` (including `newtx`, `booktabs`, and `titlesec`):

   ```powershell
   cd report
   pdflatex -interaction=nonstopmode -halt-on-error report.tex
   pdflatex -interaction=nonstopmode -halt-on-error report.tex
   ```

   The second pass resolves cross-references. The submitted PDF can be read without
   installing TeX. Tables and figures are generated automatically; narrative findings
   in `report.tex` must also be reviewed if experiment settings or data change.

   Alternatively, from `report/`, run `tectonic report.tex`. Tectonic 0.16.9 was used
   for the validated rebuild and resolves the required passes automatically.

## Scope and conventions

- Table 1 uses daily mean **0.0025% = 0.000025**, daily standard deviations
  **0.45%–4.5%**, and 252 trading days per year. The monthly extension uses the
  paper's mean **0.5%** and standard deviations **0%–20%**, for 15 and 20 years.
- Table 4 uses French industry portfolio returns: one eligible industry is selected
  each month, with equal- or value-weighted stocks inside it. The main paper
  comparison covers July 1926–December 2016. Three-month momentum first holds in
  October 1926; bonus rules first hold in January 1927.
- Bonus results use data through August 2026. Reported ten-year win rates are
  historical frequencies, with overlapping windows, before transaction costs; they
  are not established probabilities of beating the market in a future decade.
