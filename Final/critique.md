# Critique - Conservative Formula

> Historical review. The cache finding below has been resolved in the final three-pass review.
> See `FINAL_REVIEW.md` for the current validation and assignment coverage, including the added
> payout, sector and quadratic checks. Earlier numerical results and counts below are historical.

Updated 2026-10-12. Current re-review only; resolved findings and superseded reviews have been removed. The authoritative records put results-pipeline, final-notebook and final-slides in review. Reproducibility is closed; its rehearsal-command follow-up was checked with the pipeline rework.

## Open findings index

| ID | Severity | Status |
|---|---|---|
| 2026-10-11-results-pipeline/R1 | medium | Partially resolved: dependency CSVs are protected, but the diagnostics cache bypasses provenance verification. |

## Verification

Commands ran from `Final/`, without network access or commits. Review probes blocked disk mutations or redirected writers to memory. The only edits were this file and the user's newly authorized removal of the two obsolete legacy folders.

- Read-only `python -B -` calling `pytest.main(['tests', '-q', '-s', '-p', 'no:cacheprovider', '-p', 'no:logging', '--rootdir=.', '--confcutdir=.', '-k', <eight writer exclusions>, '--tb=short'])`: **171 passed, 8 deselected**. The unused `tmp_path` fixture was replaced with a nonexistent path inside Final; no directory was created.
- Five excluded result-contract tests were then executed unchanged against an in-memory filesystem: loader hash mismatch, `--only`, stale dependency provenance, modified dependency, and `--with-deps`: **5 passed**. The changed-data/source cases reject before writes; modified and unlisted dependency CSVs raise; stale dependencies are recomputed in order.
- Both excluded deck tests passed with PPTX/notes writes intercepted in memory. The sole test not independently rerun was the CRSP end-to-end build writer. The coder reports the ordinary full suite as 179 passed.
- All **73 result files** pass their manifest hashes. Compared with `out/manifest_before_rework.json`, **72 files are byte-identical**; only `critical_tests/run_meta.json` changed. All ten studies return `stale_reasons = []` against current recorded provenance.
- After legacy deletion, both notebook modes execute all **14 code cells** in memory: CRSP has 71 display objects; demo has 15, a synthetic label and no empirical abstract. The deck rebuild has **14 titled slides with notes**; every PPTX ZIP member matches the saved deck and generated notes match the saved notes. This is structural/textual verification, not a rendered visual inspection.
- The full empirical pipeline and fresh-checkout run were not repeated by the critic; they write artifacts outside the critic's review scope.

## Review: 2026-10-11-results-pipeline (implementation, 2026-10-12)

**Verdict: changes requested.** Per-study provenance, dependency CSV validation, transitive recomputation and early endpoint rejection now work. The revised rehearsal selects a supported dependency-closed set. One input route remains outside the protection required by the accepted R1 disposition.

### 2026-10-11-results-pipeline/R1 · medium · Bind the diagnostics cache to its recorded producer

**Evidence:** `research/studies/_common.py:49` returns any existing `<output>/diagnostics_universe.parquet`; it neither verifies a hash nor records the read. FMP reads that path at `research/studies/fmp.py:33`, long/short at `research/studies/longshort.py:45`, and optimization at `research/studies/optimization.py:123`. The preflight at `research/run_all.py:140` validates only declared aggregate `FILES`; `research/run_all.py:246` records only `ctx.reads`. The cache is absent from both. The rework log's claim at `experiments/2026-10-11-results-pipeline/README.md:196` that the diagnostics fingerprint covers cache lineage is therefore insufficient: it identifies the aggregate producer record, not the bytes at the chosen cache path.

**Executed counterexample:** `python -B -`, using the actual manifest, registry, `stale_reasons`, `Context.universe_cache` and `fmp.run`. An in-memory alternate output directory contains a valid Parquet cache with synthetic `date`, `group` and `mktcap` fields. File operations for that directory are virtualized; the Parquet reader decodes its bytes normally. FMP's first calculation is intercepted only to record that the supplied cache reached it and stop before further work. Output:

```text
DIAGNOSTICS_PRECHECK []
FOREIGN_CACHE_REACHED_REAL_FMP_CALCULATION True CACHE_READS_RECORDED {}
CACHE_HASH_RECORDED_IN_DIAGNOSTICS False
REAL_VIRTUAL_DIRECTORY_EXISTS False
```

The actual FMP provenance also has `inputs: {}`; the long/short and optimization records contain the replication CSV, but no cache hash.

**Failure scenario:** `--only fmp --output <existing-output-directory>` accepts a cache left by a different data/code run, while the current diagnostics aggregates pass preflight. A shared default output folder can likewise be overwritten by a separate results run. FMP, long/short or optimization can then compute from foreign exposures/forward returns and stamp the new outputs with current provenance. `--with-deps` does not help when diagnostics appears current, because it skips that producer. This does not establish that the presently saved results are wrong; their verified hashes and equivalence still hold.

**Required change:** record the cache's hash and producing data/source identity, verify them before reuse, and include the verified cache identity in each consuming study's provenance. Rebuild or reject a stale/foreign cache, including when `--output` changes. Keep licensed rows in ignored `output/`; only their hashes/metadata need recording. Add regression cases for a changed cache and an alternate output folder. No research convention change is needed.

→ planner: 2026-10-11-results-pipeline reviewed

## Review: 2026-10-11-final-notebook (implementation, 2026-10-12)

**Verdict: pass for the reporting rework.** R1–R3 are resolved; no notebook finding remains.

Executed `python -B -` to run the generated cells and capture displayed objects. The critical table now shows the stored intervals for compounded return, volatility, both Sharpe ratios, excess return, Carhart and FF5+UMD alpha, with drawdown explicitly labeled as having no CI. The 1990–2024 net-30 row includes compounded **11.2% [6.4%, 16.5%]**, volatility **13.5% [11.6%, 15.1%]**, and FF5+UMD alpha **−1.97% [−3.7%, −0.3%]**; the headline gives the alpha interval to two decimals. The independent optimizer count and generated prose agree: **3/4** selected headline intervals exclude zero, **0/12** post-sample intervals do, with the unadjusted-grid caveat. The composite is correctly defined as a mean and distinguished from the FMP sum. Both modes execute successfully, and builder-sync/security-output tests pass.

→ planner: 2026-10-11-final-notebook reviewed

## Review: 2026-10-11-final-slides (implementation, 2026-10-12)

**Verdict: pass for the slide rework.** R1 is resolved; no slide finding remains.

Executed the two `tests/test_deck.py` tests with memory-only writers. The deck derives its interval statement from the shared helper, agrees with the independent CSV count, and retains the selection qualification. ZIP-content comparison returns `DECK_ZIP_CONTENT_DIFFERENCES []`; generated notes match. The active generator builds successfully with both legacy folders absent.

**User-authorized legacy cleanup:** removed `legacy/` (2 files: obsolete WRDS connection probe and README) and `presentation/legacy/` (11 files: superseded synthetic deck, private-runtime scripts, snapshot, manifest and notes). Repository searches found no active imports or build/test dependencies on those files. Resolved deletion targets were verified inside Final and checked for reparse points before removal. Current notebook, deck, sources, results and licensed data were preserved.

**Coder documentation handoff:** remove the now-obsolete inventory sentences at `README.md:69`, `README.md:264`, `presentation/README.md:17` and `docs/ARCHITECTURE.md:28`. These files remain read-only for the critic; this cleanup note is not an unresolved implementation defect. Historical task records may retain their account of the earlier move.

→ planner: 2026-10-11-final-slides reviewed
