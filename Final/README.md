# Conservative Formula — first-draft final project

Open `conservative_formula_first_draft.ipynb` in JupyterLab or VS Code.
Install the packages in `requirements.txt`, then restart the kernel and run all cells.

The notebook is self-contained and runs offline in **demo mode**. Saved outputs use
seeded synthetic data, not CRSP or real investment results. The previous bond
assignment and its files are not inputs to this project.

For real research, prepare the two normalized CSV files specified in Section 3 of
the notebook and change `MODE` to `"crsp"`. The normalized CRSP data are not included.
The payout proxy and historical data conventions must be audited before calling
the results a replication. The notebook contains the preparation checklist.

`build_notebook.py` rebuilds the unexecuted notebook; do not run it over your edited
notebook without preserving your changes. Outputs go to `output/demo/` or
`output/crsp/` according to the selected mode.

## Presentation

The [14-slide PDF](presentation/conservative_formula_presentation.pdf)
accompanies this draft. The folder also includes speaker notes and editable PowerPoint source. All
numerical results remain clearly labeled as synthetic demonstrations.

The [presentation folder](presentation/) contains the generator source, data
snapshot, speaker notes, and rebuild instructions. Generation uses the
Codex-bundled presentation runtime documented in that folder.
