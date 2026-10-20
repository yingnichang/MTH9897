# Critique - Conservative Formula

Updated 2026-10-14. Current code review; resolved findings and superseded reviews have been removed. The previous cache-provenance finding (results-pipeline/R1) is resolved: cache bytes and producer metadata are verified, and all four consuming studies record the cache identity.

## Open findings index

| ID | Severity | Status |
|---|---|---|
| 2026-10-11-results-pipeline/R2 | medium | Open: a rejected cache destroys the consumer's previously valid results. |
| 2026-10-11-reproducibility/R2 | medium | Open: submission packaging silently omits required inputs. |
| 2026-10-11-results-pipeline/R3 | low | Open: exploratory FF3-controlled FMP results replace the primary series without a reconciled task disposition. |

## Verification and scope

The user requested review of the current code. The local handoff still names the cache rework, but the checkout also contains new factor controls, quadratic optimization, sector/payout checks and packaging. Reviewed those changes and the claims in `FINAL_REVIEW.md` as evidence, not authority. Only `critique.md` was edited; no commits, external transfers or generated artifacts.

- Ordinary read-only pytest collection is blocked by **`ModuleNotFoundError: No module named 'clarabel'`** in this installed Python 3.14 environment. Clarabel is declared in both dependency files; this is a verification limitation, not an undeclared-dependency finding.
- A second `python -B -` run used a write/network-blocking audit hook, disabled pytest cache/logging, and supplied an **import-only Clarabel stub** to collect unrelated tests. Both quadratic solver tests and fourteen artifact-writing tests were excluded: **174 passed, 16 deselected**. No solver result was fabricated or tested through the stub.
- Executed the real cache-rejection, alternate-output rebuild and completed-study checkpoint tests against a memory-only filesystem: **3 passed**. The additional runner and packaging counterexamples below also used memory-only writers.
- All **85 aggregate files** match `results/manifest.json`. All **12 studies** have current recorded data/source/dependency provenance. Diagnostics records the cache producer/hash; FMP, long/short, linear and quadratic optimization record that cache as an input. Producer source/data identities match the current checkout; environment package identity differs from the recorded Python 3.12 rebuild.
- Both generated notebook modes execute all **16 code cells** in memory without errors: CRSP produces 94 display objects; demo produces 17, with a synthetic label and no empirical abstract. Builder-sync and identifier-output tests pass.
- The full licensed-data rebuild, quadratic solver execution and document rendering were not repeated. The findings do not establish an error in the presently saved numerical results.

## Review: 2026-10-11-results-pipeline (implementation, 2026-10-14)

**Verdict: changes requested.** Cache verification resolves R1, but its placement leaves an avoidable destructive failure path. The broader changes also need a consistent research-role disposition.

### 2026-10-11-results-pipeline/R2 · medium · Validate the cache before removing valid results

**Evidence:** `research/run_all.py:213` checks dependency records without validating the cache at the selected output path. At `:234–236` it deletes the selected study's existing files before `:241` invokes the study. Only inside that invocation does `research/cache.py:41` detect modified/foreign cache bytes. Consequently `--with-deps` sees a current diagnostics record, skips rebuilding diagnostics, and then fails after deleting the consumer's outputs.

**Executed counterexample:** `python -B -`, real `run_all.main` and `cache.verified_universe`, with two lightweight synthetic studies and an in-memory filesystem. First produce valid diagnostics/consumer results and manifest, alter only the cache bytes, then run `--only fmp --with-deps`. The cache identity is unchanged; no solver is involved. Output:

```text
CACHE_FAILURE_PREFLIGHT []
CACHE_FAILURE_ERROR Diagnostics cache modified or from another run; rerun diagnostics
PREVIOUS_CONSUMER_FILE_EXISTS False
MANIFEST_STILL_REFERENCES_PREVIOUS_HASH True
MANIFEST_UNCHANGED True
REAL_VIRTUAL_DIRECTORY_EXISTS False
```

**Failure scenario:** an existing alternate output folder or a modified cache causes a routine partial rerun to erase previously usable FMP results. The old manifest still lists those now-missing files, so the saved notebook/deck can no longer load them. Atomic manifest checkpointing does not preserve the deleted result files.

**Required change:** validate the selected cache path before clearing any existing study output. With `--with-deps`, schedule the producer rebuild when needed; otherwise reject without mutations. Alternatively stage each study's outputs and publish only after successful validation. Add an integration regression proving that a failed cache check preserves the previous files and manifest, including an alternate output directory.

### 2026-10-11-results-pipeline/R3 · low · Reconcile the exploratory FMP change with its primary result labels

**Evidence:** `README.md:112–113` and `FINAL_REVIEW.md:24` call the added historical FF3 controls exploratory. However, `research/studies/fmp.py:18–21` labels the resulting factor returns, paper portfolio and metrics **primary**; `:57–64` adds the controls directly to the existing calculation. The closed specification at `experiments/2026-10-11-factor-mimicking/README.md:18–22` contains signal, size and industry exposures only. The results-pipeline record still says `changes-requested` and its final disposition calls for a small cache fix with aggregate equivalence (`:253–266`), not replacement of the FMP specification.

**Executed check:** `python -B -` reads the current manifest and compares `results/fmp/paper_metrics.csv` with `git show c902285:Final/results/fmp/paper_metrics.csv`. Output:

```text
fmp/factor_returns.csv role = primary
fmp/paper_portfolio.csv role = primary
fmp/paper_metrics.csv role = primary
K1_equal, 1929–2024, IR before = 0.5027522046502596
K1_equal, 1929–2024, IR after  = 0.5861290015915724
```

**Failure scenario:** a reader or consumer filtering on `role=primary` receives the later exploratory specification under the accepted result names. The notebook describes the controls, but the manifest and unchanged task record do not explain the change of primary method. This is a scope/handoff inconsistency, not evidence that the FF3 calculation is mathematically wrong.

**Required change:** have the planner record the expanded scope and disposition of the new method. Either retain the accepted FMP results and publish the controlled variant separately as exploratory, or explicitly supersede the primary specification and make the prose, manifest labels and comparison evidence consistent. Refresh the stale task status/log instead of using the independent review appendix to imply task acceptance.

→ planner: 2026-10-11-results-pipeline reviewed

## Review: 2026-10-11-reproducibility (implementation, 2026-10-14)

**Verdict: changes requested for the new packaging code.** The earlier shortened-rehearsal finding remains resolved.

### 2026-10-11-reproducibility/R2 · medium · Reject an incomplete private data package

**Evidence:** `package_submission.py:31` discovers raw inputs by glob, and `:35` silently removes nonexistent selected files. Its required list at `:36–40` includes only the notebook, three PDFs and normalized panel. It does not require the seven raw tables, benchmark, factors or worked examples. Yet `README.md:75` and the archive's own run instructions start with a data rebuild; `crsp_pipeline/build.py:14–20` requires every raw table. ZIP CRC validation at `package_submission.py:57` cannot detect an omitted file.

**Executed counterexample:** `python -B -` calls the actual `package_submission.main()`, with only `data/raw/msf.parquet` made absent through the file predicate. The ZIP writer captures member names in memory, and output-directory/stat operations are intercepted; no archive is created or overwritten. Output:

```text
PACKAGING_RETURNED_SUCCESS True
MISSING_MSF_INCLUDED False
CAPTURED_FILES 187
```

**Failure scenario:** someone with a normalized panel but incomplete raw downloads receives a success message and submits a ZIP that fails at the first documented rebuild command. Missing benchmark/factor/worked-example files can similarly prevent research or the advertised input-hash checks.

**Required change:** build an explicit required input inventory from the data pipeline's raw-table contract and `data/manifest.json`, verify existence and recorded hashes before opening the output archive, and fail with the missing/mismatched paths. Add packaging regression cases for an absent raw table and a missing normalized auxiliary input. Do not silently downgrade a full-rebuild package to a cached-results-only package.

→ planner: 2026-10-11-reproducibility reviewed
