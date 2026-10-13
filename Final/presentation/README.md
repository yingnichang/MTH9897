# Presentation

**Authors:** Yingni Chang and Yikai Shen

The final deliverable `conservative_formula.pdf` (18 slides, 16:9) and `speaker_notes.md` (one section per slide) are generated
from the tracked results in `results/` through the hash-checked loader:

```bash
python presentation/build_pdf.py      # needs requirements.txt and results/ (python -m research.run_all)
```

The slides use the same tables and figures as the notebook. Numbers are read through `research.summary`
and the result loader; the linear-optimization chart is drawn from its saved grid table.

The presentation covers the original rule, payout and industry positioning, costs, diagnostics and
alternative portfolio rules. The speaker notes explain the results and the limits of the comparisons.

`build_pdf.py` invokes `build_deck.py` for shared content, then writes a PDF with
searchable text and tables. No LibreOffice installation is required. The PPTX is
an intermediate editable version; submit the PDF. The exporter checks textbox
and table height and expands wrapped table rows to avoid clipping.

For visual checks, render with `pdftoppm -scale-to 1400 -png
presentation/conservative_formula.pdf presentation/build/check`.
`render_previews.mjs` optionally renders PNG previews through `@oai/artifact-tool`.
