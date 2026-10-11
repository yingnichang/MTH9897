# Critique - Conservative Formula

Updated 2026-10-10. Keep unresolved findings and the latest batch review here; remove verified fixes. Dispositions and detailed implementation logs belong in the task records and memory.

## Open findings index

**No new findings blocking acceptance of the five reviewed tasks.** The old Phase 2 selection, signals, holding-return and calendar findings are fixed and have been removed. These carried-forward project issues remain outside this batch; their evidence and closure criteria are in the [issue register](memory/known_issues.md).

| ID | Severity | Status / remaining change |
|---|---|---|
| DATA-003, DATA-006 | medium | Open: quantify share-class switching and investigate the remaining dividend-amount discrepancies. |
| DATA-005 | medium | Open: qualify the public frozen-release claim or record supporting release metadata; an observed coverage endpoint is insufficient. |
| RS-001 | critical | Open: deliver the required factor diagnostics, including neutralized exposures, IC/decay, persistence, deciles, hit rates and factor-mimicking portfolios. |
| RS-002 | high | Open: complete the paper comparison, speculative portfolio, attribution and deviations table. The historical mechanics run now exists; paper reconciliation remains. |
| RS-003, RS-004 | high | Open: finish trading/reporting requirements and a declared improvement with paired, dependence-aware evaluation. The new rebalance trade log is progress, not the full reporting deliverable. |
| RS-005, ENV-002 | high | Open: make the empirical presentation/export path runnable and verify access to its rendering dependency. |
| ENV-003 | medium | Open: settle the reproducible dependency/submission contract. |

DATA-011/012 limitations, the RS-006 research tests, and minor DATA-004/ENV-001 items remain in the issue register. They are not new findings from this review.

## Batch verification

Reviewed the five records whose authoritative status is `in-review`; the planner's board still needs its normal post-review synchronization. Judged against each task's success criterion, `Instructions.md`, the paper transcription in `docs/DATA_CONVENTIONS.md`, and adopted DATA-001/002/010, NB-007 and RS-006 decisions. The logged fixture adjustment, shared checks and counts-only exports are within the batch's scope.

Independent read-only run: **93 passed, 1 deselected**. Tests used `python -B -`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, and `pytest.main(['tests', '-q', '-s', '-p', 'no:cacheprovider', '-p', 'no:logging', '--rootdir=.', '--confcutdir=.', '-k', 'not test_end_to_end_build_writes_outputs_and_manifest', '--tb=short'])`, with writes and network access blocked. Pipeline, research, builder and test files were stable throughout. The excluded test writes build artifacts; the coder separately records 94 passing tests. No fresh notebook kernel, extraction or artifact rebuild was launched by the critic; saved executions were inspected and the engine was replayed in memory without reporting performance statistics.

## Review: 2026-10-10-research-engine (implementation, 2026-10-10)

**Verdict: pass. No outstanding findings.** `research/engine.py:171,190,294` implements the adopted selection order, holdings rule and `ret_hold` accounting. The real-engine history-order, missing-signal partition, ties, small-universe, stale-carry and price-ratio tests pass. Shuffling candidate order leaves selected weights and counts unchanged.

Recomputed all **2,464 formation/strategy rows**, matching `output/crsp/crsp_draft_formation_audit.csv`. Conservative's **352** formations also match the smoke file and pipeline history/universe counts; the smallest low-volatility pool is **196**, with 100 selected at every formation. The independent eight-month synthetic dollar-book calculation, including sales, purchases, fees, nonzero cash interest and terminal cash, matches the engine's net returns to **2.22e-16** and its traded notional to **1e-14**. The smoke-run difference from the earlier approximate holding count is documented and not material to this criterion.

→ planner: 2026-10-10-research-engine reviewed

## Review: 2026-10-10-notebook-signals (implementation, 2026-10-10)

**Verdict: pass. No outstanding findings.** `research/engine.py:142` preserves all original columns and rows while attaching signals by a one-to-one key merge. Full-panel replay preserved **3,954,476 rows**, expanding 36 columns to 41, in **17.82 seconds**. Re-ran `runpy.run_path("experiments/2026-10-10-notebook-signals/compare_loop_crsp.py")` via `python -B -` under the read-only guard: **200 securities / 27,309 rows**, zero NaN-pattern mismatches, maximum absolute difference **5.33e-15** across the five signals. The hand-calculation, future-input isolation and deliberately leaky-signal rejection tests pass. The notebook and tests no longer retain their old production/reference loops.

→ planner: 2026-10-10-notebook-signals reviewed

## Review: 2026-10-10-calendar-validation (implementation, 2026-10-10)

**Verdict: pass. No outstanding findings.** `research/engine.py:269` enforces the requested benchmark calendar and first/quarter-end targets. The named failure fixtures, shared Section 7 checks, all-cash flag and second-rebalance reconciliation pass. An additional counterexample using `p, b, targets, start, end = checks.calendar_case('ok')` and `engine.backtest(p, b.drop(end), targets, start, end)` raises `Benchmark lacks 1 month(s) in the window 2020-01-31..2020-06-30; first missing 2020-06-30`.

The builder imports the required constants from config, uses `CF_MODE`/`CF_END`, and calls the shared fixture checks without indexing real-security rows. The public run instructions document the switch. Both saved notebooks match the current builder's source through the passing sync check and direct demo/CRSP source comparison.

→ planner: 2026-10-10-calendar-validation reviewed

## Review: 2026-10-10-crsp-notebook-run (implementation, 2026-10-10)

**Verdict: pass for the Phase 2 mechanics gate. No outstanding findings.** The demo and separate CRSP notebook each contain **11 code cells**, execution counts **1-11**, and **zero error outputs**. Their hashes match the task record (`ba9f5e2019517ffa...`, `07d6b0e3c97c90f2...`); the tracked notebook remains the demo artifact. Saved gate: **11/11 true**.

Replayed all seven strategies in memory through **1929-01 to 2016-12**, using the current engine. Every saved diagnostics field matches, including **1,056 months per strategy**, zero all-cash months, and Conservative's **58 stale-carry / 0 price-ratio position-months**. All 352 Conservative formation counts match the smoke run. No 2017+ holding return entered this replay, and no performance statistic was reported or interpreted. The result establishes mechanics, not paper agreement or investment merit.

→ planner: 2026-10-10-crsp-notebook-run reviewed

## Review: 2026-10-10-ff5-factors (implementation, 2026-10-10)

**Verdict: pass against the specified data contract. No outstanding implementation findings.** Recomputed `build_benchmark` and `merge_ff5` from local raw files; `pd.testing.assert_frame_equal` matches the saved eight-column factor file and confirms that the FF3/UMD columns and benchmark are unchanged. RMW/CMA are missing before **1963-07**, complete from then through **2024-12**, with **738 overlap months**. Reproduced the reported maximum market-factor difference (**0.0008**), identical rf, and SMB/HML correlations (**0.981153 / 1.0**). The discrepancy is reported rather than hidden.

Rehashed **10 source files, 7 raw inputs, 3 normalized outputs and 8 audits**: zero manifest mismatches. Comparison with the prior tracked manifest confirms the panel, benchmark, all eight audits and six original raw extracts are unchanged. Current manifest SHA-256: `2db51cf898e033deea1783ddb8c29334f705d1498f5361a94f95f92b67aaf399`; panel remains `84e3148292b901400bb33450187b2c22c7fe6f7ce104c4b5d20812e9eb131cdc`.

**Planner carry-forward, already raised in the task record:** the merged file retains FF3 SMB/MKT-RF and adds FF5 RMW/CMA (`crsp_pipeline/normalize.py:212-239`; task record lines 90-96). Resolve the factor-set choice before labeling a later regression FF5+UMD. This does not block the explicitly specified eight-column extract/merge task, which includes no regression. Also synchronize the planner-owned convention/status documents at triage.

→ planner: 2026-10-10-ff5-factors reviewed
