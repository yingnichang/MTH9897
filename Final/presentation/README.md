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
alternative portfolio rules. The speaker notes are full read-aloud scripts for all 18 slides, with
presenter cues, transitions, per-slide timing and six likely questions with suggested answers.
The script is about 2,000 words; allow 15-18 minutes with short pauses. An optional presenter split
assigns slides 1-9 to Yingni and slides 10-18 to Yikai.

The same scripts are embedded in the editable PPTX notes. A separate rehearsal PDF is saved as
`output/pdf/conservative_formula_speech_notes.pdf`. Regenerate it and the Markdown script with:

```bash
python presentation/build_speech_notes.py
```

`speech_notes.py` holds the speaking text and reads figures from the saved results. Edit that source
and rebuild the notes and deck when changing the script.

For a shorter talk, `speaker_notes_short.md` gives a few sentences per slide. The matching PDF is
`output/pdf/conservative_formula_short_speech_notes.pdf`. It explains the difference between the
36-bps alpha and 52-bps market-excess break-even costs. Generate both short versions with
`python presentation/build_short_speech_notes.py`; the detailed script remains available separately.

`build_pdf.py` invokes `build_deck.py` for shared content, then writes a PDF with
searchable text and tables. No LibreOffice installation is required. The PPTX is
an intermediate editable version; submit the PDF. The exporter checks textbox
and table height and expands wrapped table rows to avoid clipping.

For visual checks, render with `pdftoppm -scale-to 1400 -png
presentation/conservative_formula.pdf presentation/build/check`.
`render_previews.mjs` optionally renders PNG previews through `@oai/artifact-tool`.
