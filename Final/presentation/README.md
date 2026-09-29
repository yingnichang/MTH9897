# Conservative Formula presentation

`conservative_formula_presentation.pdf` is the 22-slide presentation accompanying
the first-draft notebook. The PowerPoint file is the editable source. Presenter
notes appear inside that source and in `speaker_notes.md`.

The expanded version adds the economic rationale for combining signals,
worked payout and stock-ranking examples, a transaction-cost calculation,
data-bias controls, evaluation periods, explanations of the performance
measures, and balanced interpretation of the synthetic results. Suggested
speaking time is approximately 18–22 minutes, excluding questions.

## Regenerate the PDF

`export_pdf.mjs` renders each PowerPoint slide at 2560 × 1440 pixels, then calls
`images_to_pdf.py` to create a PDF with one 16:9 landscape page per slide.
This preserves the visual layout. PDF text and charts are flattened images.
Speaker notes remain in the separate Markdown file.

Set `ARTIFACT_TOOL_MODULE` as described below and `RUNTIME_PYTHON` to Python with
`reportlab` and `pypdf` installed, then run:

```sh
node export_pdf.mjs
```

Optional positional arguments specify a different input PPTX and output PDF.
Intermediate images go to the ignored `build/pdf-pages/` directory.

**All displayed numerical results use synthetic demonstration data.** This is a
presentation of the current draft, not a completed CRSP replication. Replace the
results and revise the narrative after the empirical study is complete.

## Generator files

- `generate_slides.mjs`: JavaScript source for the entire presentation.
- `slide_data.json`: committed numerical snapshot of notebook demo outputs.
- `export_slide_data.py`: standard-library Python script that refreshes the snapshot.
- `finalize_slides.mjs`: packages chart workbooks and validates a separately staged deck.
- `deck_manifest.json`: slide count and native chart/table locations, generated alongside each candidate.

No charts, data, or helper assets need to be downloaded to regenerate the deck.
The PowerPoint opens normally without the generation runtime.

## Runtime requirement

The generator uses **Node.js and the Codex-bundled `@oai/artifact-tool` 2.8.59**.
This is a private bundled dependency, not a package to install from public npm.
Run in a Codex environment that provides it, or point `ARTIFACT_TOOL_MODULE` to
the supplied `@oai/artifact-tool/dist/artifact_tool.mjs` file. The script does not
include the proprietary runtime in this repository. It uses the Arial font.

If the package is already resolvable:

```sh
node generate_slides.mjs
```

Otherwise, in PowerShell, replace the example path with your bundled module path:

```powershell
$env:ARTIFACT_TOOL_MODULE = 'C:/path/to/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs'
node generate_slides.mjs
```

Use the bundled Node executable if `node` is unavailable on your PATH.
The script writes `conservative_formula_presentation.pptx` and `speaker_notes.md`
next to itself. `DECK_OUTPUT` can override the output PPTX path. `PREVIEW_DIR`
optionally exports slide PNGs for visual inspection. Rebuilding overwrites those
generated outputs, so preserve any manual edits first.

### Packaging editable chart data

The committed deck also includes embedded Excel workbooks for its chart values.
To repeat this packaging step in Codex, set `PRESENTATIONS_SKILL_DIR` to the
installed presentation skill directory, `RUNTIME_PYTHON` to bundled Python,
and `RUNTIME_NODE_MODULES` to the bundled Node package directory. Generate the
candidate with `DECK_OUTPUT=./build/candidate.pptx`, then run:

```sh
node finalize_slides.mjs build/candidate.pptx rebuilt/conservative_formula_presentation.pptx
```

Both paths must be inside the current working directory (or `DECK_WORKSPACE`).
Keep the generated `deck_manifest.json` next to the candidate so the finalizer
checks the chart and table locations for the current slide order.
The finalizer requires a new output path and never overwrites an existing deck.
It writes private validation records to `.slide-validation/`. The intermediate
generator output uses editable native charts with literal data. Finalization
adds the portable workbooks included in the committed deliverable.

## Refresh the numerical snapshot

Run the notebook in demo mode, then:

```sh
python export_slide_data.py --outputs ../output/demo
node generate_slides.mjs
```

The exporter records source CSV SHA-256 hashes. Both scripts reject empirical
input mode because the current narrative explicitly describes a simulation.
For an empirical presentation, update the slide text, coverage, source notes,
and conclusions together with the data.
