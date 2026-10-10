# Critique - Conservative Formula

Updated 2026-10-10. Keep this file focused on unresolved findings and the latest review. Remove findings after verifying their fixes; dispositions and implementation evidence belong in the task records and memory.

## Open findings index

These are carried-forward project issues, not blockers for the completed missing-return pipeline task. The [issue register](memory/known_issues.md) holds their detailed evidence and closure criteria. Planned work is not being presented as implemented.

| ID | Severity | Status / remaining change |
|---|---|---|
| DATA-001, DATA-002; NB-001, NB-007 | high | In progress: the notebook still uses the old universe/selection order and `ret_total`. Implement the adopted history-first selection, partition-before-ranking and `ret_hold` consumption in the research engine. |
| NB-002 | high | Open: reject missing initial/final benchmark months and missing initial/rebalance targets; silent all-cash or shortened backtests must fail. |
| NB-003, NB-004, NB-005, NB-006 | medium | Open: integrate pipeline signals by a checked key merge, test the real engine, replace fragile row-index checks, and remove duplicated constants/stale references. |
| DATA-003, DATA-006 | medium | Open: quantify share-class switching and investigate the remaining dividend-amount discrepancies before claiming those checks are reconciled. |
| DATA-005 | medium | Open: coverage through December 2024 does not identify the database release. Qualify the public frozen-release claim or record supporting metadata. |
| RS-001 | critical | Open: deliver the required factor diagnostics, including neutralized exposures, IC/decay, persistence, deciles, hit rates and factor-mimicking portfolios. |
| RS-002 | high | Open: complete the empirical paper comparison, including the speculative portfolio, attribution and a deviations table. The required historical portfolio run is still pending. |
| RS-003, RS-004 | high | Open: complete trade/reporting requirements and a declared improvement with a paired, dependence-aware evaluation. |
| RS-005, ENV-002 | high | Open: make the empirical presentation/export path runnable and verify access to its rendering dependency. |
| ENV-003 | medium | Open: settle the reproducible dependency/submission contract; recorded package versions do not themselves provide a runnable environment. |

The newly recorded DATA-011/012 limitations (straddling-gap bias and extreme price ratios outside the universe), RS-006 research extension, and minor DATA-004/ENV-001 items remain in the issue register. They are not new findings from this recheck. The next implementation review covers the released Phase 2 batch when it is handed off.

## Review: 2026-10-10-missing-return-convention (implementation, 2026-10-10)

**Verdict: pass. No outstanding findings for this task.** The saved DATA-010 rebuild, public documentation and final Results now satisfy the acceptance checks left by the previous review.

Independent read-only verification:

- Rehashed all **10 pipeline source files, 3 normalized outputs and 8 audits** against `data/manifest.json`: **zero mismatches**.
- `validate_panel` passes on **3,954,476** saved rows. Recomputing `add_holding_returns` reproduces both saved holding-return columns exactly: **175** price-ratio rows, **107,341** stale-carry rows, **26,745** first-row NaNs and **3,820,215** observed CRSP returns.
- `pd.testing.assert_frame_equal(audit.missing_returns(panel), pd.read_csv('data/audit/missing_returns.csv'))` passes. There are **3** price-ratio universe holding months; the nine original criterion totals remain **447 / 356 / 403 / 239 / 208 / 21 / 403 / 367 / 376**, and the non-spanning split remains **7 / 2**.
- `README.md:58-69,102` now describes the price-ratio rule, its three-month bound and remaining limitations. The task record's DATA-010 implementation/results and final triage are at `experiments/2026-10-10-missing-return-convention/README.md:211,356,469`; `docs/DATA_CONVENTIONS.md:39-40,64-77` agrees with the implemented convention.
- **66 tests passed, 1 deselected** in the critic's read-only run. The excluded test writes build artifacts; the task record separately reports the coder/planner's full runs. Pipeline and test file hashes were stable throughout this run.

Verification ran locally with `python -B -`. Tests used `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and `pytest.main(['tests', '-q', '-s', '-p', 'no:cacheprovider', '-p', 'no:logging', '--rootdir=.', '--confcutdir=.', '-k', 'not test_end_to_end_build_writes_outputs_and_manifest', '--tb=short'])`, under a guard rejecting writes and network access. No extraction, rebuild or portfolio backtest was run by the critic.

Verified manifest SHA-256: `d1adf55e9b05ca33a376d8c07fc5531c60479b17ce897fb7a8cfab0eb23d5ba6`.
Verified panel SHA-256: `84e3148292b901400bb33450187b2c22c7fe6f7ce104c4b5d20812e9eb131cdc`.

→ planner: 2026-10-10-missing-return-convention reviewed
