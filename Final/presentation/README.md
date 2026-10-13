# Presentation

The final deliverable `conservative_formula.pdf` (18 slides, 16:9) and `speaker_notes.md` (one section per slide) are generated
from the tracked results in `results/` through the hash-checked loader:

```bash
python presentation/build_pdf.py      # needs requirements.txt and results/ (python -m research.run_all)
```

Every number on a slide is formatted from `research.summary.numbers()` or read from a results table, and the figures are
the PNGs in `results/`, except the linear-optimization slide's chart, drawn from its verified grid table.
No slide carries a security identifier column (the builder checks every table header).

The final review adds slides on net payout, industry allocation versus stock selection, and quadratic
mean-variance optimization. These extensions are labeled separately from the paper's original rule.

`build_pdf.py` invokes `build_deck.py` for shared content, then writes a PDF with
searchable text and tables. No LibreOffice installation is required. The PPTX is
an intermediate editable version; submit the PDF. The exporter checks textbox
and table height and expands wrapped table rows to avoid clipping.

For visual checks, render with `pdftoppm -scale-to 1400 -png
presentation/conservative_formula.pdf presentation/build/check`.
`render_previews.mjs` optionally renders PNG previews through `@oai/artifact-tool`.
