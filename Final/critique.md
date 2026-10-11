# Critique - Conservative Formula

Updated 2026-10-11. Current Phase 3 batch review only; verified fixes and superseded reviews have been removed. Task records retain dispositions. Other unfinished project work remains in [memory/known_issues.md](memory/known_issues.md); it is not a new finding against this batch.

## Open findings index

| ID | Severity | Status |
|---|---|---|
| 2026-10-10-factor-attribution/R1 | medium | Open: distinguish a difference of net long-only returns from a cost-inclusive CMS spread; also affects critical-tests. |
| 2026-10-10-critical-tests/R1 | medium | Open: complete the specified uncertainty reporting for 2017-2024 summary statistics. |

## Verification

Reviewed the three authoritative `in-review` records against their success criteria, `Instructions.md`, the paper transcription in `docs/DATA_CONVENTIONS.md`, and adopted decisions, including RS-006 and the FF5 factor-set decision. The board still awaits the planner's normal synchronization. No new portfolio rule or parameter tuning was found.

Read-only tests: **109 passed, 1 deselected**. Command: `python -B -` with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, a write/network-blocking audit hook, and `pytest.main(['tests', '-q', '-s', '-p', 'no:cacheprovider', '-p', 'no:logging', '--rootdir=.', '--confcutdir=.', '-k', 'not test_end_to_end_build_writes_outputs_and_manifest', '--tb=short'])`. The excluded test writes build artifacts; the coder records 110 passing tests. Source/test hashes were unchanged during the run. The notebook sync test intercepts its writer; its printed "Created" message did not create a notebook.

Replayed the calculation sections of both task scripts through `python -B -`, using their parsed AST, capturing CSV exports in memory and blocking filesystem writes/network access. No notebook, pipeline build or extraction was launched. Saved plots were inspected separately. Only `critique.md` was edited.

## Review: 2026-10-10-paper-replication (implementation, 2026-10-11)

**Verdict: pass. No outstanding findings.** The new Speculative and standalone selectors match the fixed comparison spec (`research/engine.py:195`). Their fixtures pass, and shuffling a real formation's input rows leaves all four new controls unchanged.

The replay reproduces **11 runs of 1,056 months**, **1,760 formation rows**, the monthly returns, decade table, Table 4, pct10 sensitivity, reconciliation and turnover decomposition without numerical mismatches. All **42 numeric Table 1 fields** also match an independent recalculation from the saved monthly series. The cost reconciliation is within the required 0.1 percentage point annually at both cost levels. The turnover gap is discussed without retuning; paper targets remain explicitly provisional.

DATA-011 is now quantified: **25** held straddling positions, all with resumption prices, **14** with cash distributions; mean lost move **-4.5278%**, median **0%**. The weight-sum approximation reproduces **+0.01503 percentage point/year** of optimistic bias. This is an approximate diagnostic, not a rerun with an alternative execution convention. The saved figures have the required gross/log-scale and partial-decade labels.

→ planner: 2026-10-10-paper-replication reviewed

## Review: 2026-10-10-factor-attribution (implementation, 2026-10-11)

**Verdict: numerical implementation passes; changes requested for R1's result labeling and unresolved interpretation.** All **28** saved attribution rows match an independent QR-based OLS calculation and HAC(12) alpha-influence calculation, including annual alpha, standard error, t-statistic, confidence interval and factor loadings. FF5 rows use **642 months**.

Rebuilding the factor merge in memory from the local raw files reproduces the **1,182 x 10** saved file and unchanged benchmark. FF3/UMD values are unchanged; all four added FF5 columns are missing before July 1963 and complete thereafter; HML identity holds in **738** overlapping months. Rehashed **21** manifest-listed source/output/audit files: zero mismatches; the panel remains `84e31482...`. The previous concern about a hybrid FF5 model is resolved.

### 2026-10-10-factor-attribution/R1 - medium - "net CMS" credits back the short leg's costs

**Evidence:** `experiments/2026-10-10-factor-attribution/run_attribution.py:32` passes each leg's net long-only return into the CMS subtraction at `research/stats.py:69`. The main CMS rows are labeled `net 30 bps`; the cost-deducting alternative is only a diagnostic (`run_attribution.py:38`). The same labels/definition propagate at `experiments/2026-10-10-critical-tests/run_critical.py:70`. This ambiguity is already acknowledged in the attribution record at `README.md:99`; it needs a planner disposition, not another undisclosed convention change.

**Executed counterexample:** `python -B -`, using this stdin:

```python
import pandas as pd
from research import report
idx = pd.date_range('2000-01-31', periods=3, freq='ME')
g = pd.Series(0.01, index=idx)
c = report.net_from_gross(pd.DataFrame({'gross': g, 'traded_notional': 0.2}), 30)
s = report.net_from_gross(pd.DataFrame({'gross': g, 'traded_notional': 0.8}), 30)
print(round((c-s).iloc[0], 6), round((c-2*g+s).iloc[0], 6))
```

Output: **`0.001818 -0.00303`**. Equal gross returns produce a positive spread when the higher-cost Speculative return is subtracted. Deducting both legs' costs produces a loss. In the actual `out/table2.csv:24`, CMS Carhart alpha rises from **7.8103% gross** to **7.8636% "net"**; the existing both-legs diagnostic is **5.8550%**.

**Failure scenario:** a reader selects the primary CMS `net 30 bps` row to answer whether alpha survives costs, as the task's goal requests, and treats the short leg's costs as a benefit. Correct regression arithmetic does not make that row a cost-inclusive long-short return. The implementation follows the literal spread specification; the specification and output interpretation need reconciliation.

**Required change:** retain the calculated spread if useful, but label it explicitly as the **difference of net long-only returns**, not net CMS performance, in both tasks' CSVs and Results. The planner must resolve which CMS cost measure answers RS-006 before acceptance. Keep the existing both-legs diagnostic's assumptions explicit; this finding does not require building the deferred long-short trading engine or silently changing the frozen portfolio series.

→ planner: 2026-10-10-factor-attribution reviewed

## Review: 2026-10-10-critical-tests (implementation, 2026-10-11)

**Verdict: changes requested for R1 and the shared CMS-labeling finding above.** The numerical replay matches all **60 subperiod rows**, **10 break-even rows**, and **2,066 rolling rows**, with **1,152 months** per underlying strategy. All eight compared 1929-2016 series are bit-identical to the replication outputs. Independent closed-form break-even roots differ from the saved bisection results by at most **0.2241 bp**, within the 0.5 bp criterion. Period counts and FF5 coverage agree with the specification.

The current **16 source hashes** match both `source_hashes_before.txt` and `out/run_meta.json`; the manifest hash also matches. The recorded first post-2016 computation is **2026-10-11T00:50:37Z**. This verifies consistency with the saved freeze evidence, not an independently observed historical timestamp.

### 2026-10-10-critical-tests/R1 - medium - post-sample summary estimates lack required uncertainty

**Evidence:** the spec at `experiments/2026-10-10-critical-tests/README.md:47` requires a standard error and 95% CI next to every 2017-2024 point estimate; success criterion 3 at line 58 requires the listed statistics and CIs. `run_critical.py:102` adds the summary statistics, but lines 107-120 calculate uncertainty only for excess-versus-market returns and factor alphas. `out/subperiods.csv:38` therefore reports Conservative's **11.00% CAGR**, **11.88% arithmetic return**, **16.63% volatility**, Sharpe ratios and drawdown without their uncertainty.

**Executed artifact check:** `python -B -`, using this stdin:

```python
import pandas as pd
s = pd.read_csv('experiments/2026-10-10-critical-tests/out/subperiods.csv')
p = s.loc[s.period.str.startswith('2017')]
metrics = ['compounded', 'arithmetic', 'volatility', 'sharpe_paper', 'sharpe_excess', 'max_drawdown']
print(len(p), p.months.unique().tolist())
print({m: [c for c in s if c.startswith(m+'_') and ('se' in c or 'ci' in c)] for m in metrics})
```

Output: **`12 [96]`**; every metric maps to **`[]`**. The 96-month warning and the alpha/excess-return confidence intervals are present; they do not provide uncertainty for the other point estimates.

**Failure scenario:** the post-sample comparison carries those summary estimates into the final report as if the promised uncertainty analysis were complete. In particular, the raw arithmetic-return estimate has no interval even though it is one of the explicitly specified statistics.

**Required change:** complete the required post-sample uncertainty fields and associated Results, with a documented dependence-aware method and validation for the nonlinear statistics. The planner should resolve any intended narrower interpretation of "every point estimate" explicitly in the disposition. Preserve the frozen return series and record this as a post-freeze reporting correction rather than overwriting the original freeze claim.

→ planner: 2026-10-10-critical-tests reviewed
