# Presentation

**Authors: Yingni Chang and Yikai Shen**

The submission deck is `conservative_formula.pdf`: 22 pages, 16:9, with searchable text and tables.
Run from `Final/`:

```bash
python presentation/build_pdf.py
python presentation/build_speech_notes.py
python presentation/build_short_speech_notes.py
```

`build_pdf.py` reads the original PPTX as a layout template. It never writes a new PowerPoint file.
`numeric_views.py` supplies verified tables for the historical pages. `research/feedback_summary.py` supplies
the five added pages and the extended report text. The former professor-questions slide is excluded from the final submission.
`build_deck.py` is a compatibility entry point for the same PDF workflow. Keep the original PPTX available as a
source input; its embedded old notes are superseded by the current separate speech notes.

Pages 1-17 cover the existing replication and experiments. Pages 18-22 add the 2017-2024 cost grid, time-series
plots, lagged-spread model, UK data and UK/US results. The final deck ends with the comparison results.

`speaker_notes.md` and `output/pdf/conservative_formula_speech_notes.pdf` provide a full script for all 22 pages.
The script is about 2,400 words; allow 19-21 minutes with pauses. The shorter script in `speaker_notes_short.md`
and `output/pdf/conservative_formula_short_speech_notes.pdf` is about 900 words, or 7-9 minutes with pauses.
An optional presenter split is Yingni on pages 1-9 and Yikai on pages 10-22.

Numbers and figures come from hash-checked aggregate results. The UK comparison identifies local currencies,
different market benchmarks, missing terminal payments and the separate purchase-tax scenario. No UK alpha is
estimated using US factors. Render the final PDF with Poppler for visual review.

The approved Navy & Teal Research design uses a navy title band, warm cream background, teal accents, and consistent native tables. The cover and cost-summary page use dedicated layouts. `chart_theme.py` redraws presentation charts from the same hash-checked aggregate data; it does not rerun or modify the backtests. Presentation generation code remains in GitHub for audit and is excluded from the submission archive.
