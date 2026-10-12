# Presentation

The deck `conservative_formula.pptx` (14 slides, 16:9) and `speaker_notes.md` (one section per slide) are generated
from the tracked results in `results/` through the hash-checked loader:

```bash
python presentation/build_deck.py      # needs python-pptx (requirements.txt) and results/ (python -m research.run_all)
```

Every number on a slide is formatted from `research.summary.numbers()` or read from a results table, and the figures are
the PNGs in `results/`. No slide carries a security identifier column (the builder checks every table header).

**PDF (optional).** With LibreOffice installed:
`soffice --headless --convert-to pdf --outdir presentation presentation/conservative_formula.pptx`.
No PDF is produced by the build itself.

`legacy/` holds the superseded first-draft deck (synthetic demonstration data) and its generator, which requires a private
runtime; it is not on any build path.
