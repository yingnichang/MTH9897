"""Build the self-contained first-draft notebook. No external data downloads."""
from pathlib import Path
import nbformat as nbf
from textwrap import dedent

ROOT = Path(__file__).resolve().parent
cells = []
def md(s): cells.append(nbf.v4.new_markdown_cell(dedent(s).strip()))
def code(s): cells.append(nbf.v4.new_code_cell(dedent(s).strip()))

md(r'''
# Does the Conservative Formula Still Work?
## Replication design and extensions of a simple equity strategy
**MTH 9897 · Project 8 · First draft · September 29, 2026**
**Team / authors:** [Add names and team number]

> **Draft status: executable research prototype, not an empirical replication.**
> The saved outputs use seeded, synthetic stock data. No WRDS equity extract was available for this draft.
> The existing course CSVs in the workspace contain corporate bonds and are not used here.
> Every chart and results table is labeled accordingly. Do not describe these outputs as evidence that the strategy works.

**Primary paper:** Pim van Vliet and David Blitz (2018), *The Conservative Formula: Quantitative Investing Made Easy*,
[March working paper, SSRN 3145152](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152).
The published version lists David Blitz and Pim van Vliet, *The Journal of Portfolio Management*, 44(7).

### Abstract
This project asks whether combining low volatility, momentum, and shareholder payouts produces a useful equity selection rule.
The intended study will replicate a quarterly strategy in US stocks using historical CRSP data, then evaluate recent-period
performance, the incremental contribution of each signal, and sensitivity to trading costs. This first draft specifies the data
contract and research design and implements the selection and portfolio accounting in Python. A synthetic panel demonstrates
that the workflow runs; it does not establish profitability or reproduce the paper's estimates. The empirical conclusions remain
open until the historical equity data and signal definitions have been audited.

### How to run
Use Python 3.10+ with `numpy`, `pandas`, `matplotlib`, and `ipython` in a Jupyter environment.
Run **Kernel → Restart Kernel and Run All Cells**. The default demo mode needs no credentials or downloads.
It generates its own data and saves clearly named outputs under `output/demo/`.
For real research, follow Section 3 to build the CRSP inputs and start the kernel with the environment variable `CF_MODE=crsp`
(optionally `CF_END=YYYY-MM-DD` for the last return month; the default is December 2016, the end of the paper's sample).
Missing real files cause an error, never a silent demo fallback.
''')

md(r'''
## 1. Research question and economic intuition
The main question is: **does combining the three signals improve risk-adjusted performance relative to simple alternatives?**
Low volatility favors stable stocks; momentum favors recent winners; net payout yield favors companies distributing cash or
reducing their share count rather than issuing more equity. Combining these signals could offset weaknesses of an individual
screen, but that is a hypothesis to test, not an assumption embedded in the conclusions.

The paper selects 100 stocks from a universe of the largest 1,000, first screening on 36-month volatility and then ranking on
momentum and payouts. Holdings are equally weighted and refreshed quarterly. See the
[paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152) and
[Robeco's explanatory guide, pages 5–6](https://www.robeco.com/docm/docu-202302-guide-to-conservative-investing.pdf).

**Pre-specified hypotheses**
1. The combined portfolio has a higher Sharpe ratio and a less severe maximum drawdown than the market benchmark.
2. Removing momentum or payouts weakens performance relative to the full combination.
3. Results weaken after trading costs and may differ in the post-publication period.

These comparisons may reject the hypotheses. Negative findings and replication discrepancies are legitimate results.
The goal is a transparent assessment rather than finding parameters that manufacture outperformance.
''')

md(r'''
## 2. Scope, timing, and differences from an exact replication
The course brief requests a US CRSP backtest beginning in 1929. The empirical target is January 1929 through the latest complete
calendar year available, with 1926–1928 history for initialization. Freeze an extract date and document its coverage.
The demo instead uses 2000–2025 artificial observations and starts investing in January 2003 after a 36-month warm-up.

| Component | First-draft convention |
|---|---|
| Universe | Point-in-time eligible US common stocks with 36 consecutive monthly returns; the largest 1,000 of these by month-end market cap |
| Historical shortfall | If fewer than 1,000 such stocks exist (before mid-1964), use all of them and report counts; never use today's constituents |
| Volatility | Sample standard deviation of 36 consecutive monthly total returns, annualized by √12 |
| Momentum | 11 compounded monthly price returns, excluding the most recent formation month |
| Dividend yield | Trailing 12-month split-adjusted cash dividends / current split-adjusted price |
| Net issuance proxy | Current split-adjusted shares / their trailing 24-month mean − 1 |
| Net payout proxy | Dividend yield minus the net issuance proxy; larger means more payouts / fewer new shares |
| Selection | Lower-volatility half of the universe; within it, average ranks on momentum and payout among stocks with both signals; keep best 100 |
| Rebalancing | Signals at March/June/September/December end; first earned return is the following month |
| Between rebalances | Weights drift with total returns; dividends are reinvested in the paying stock |
| Missing monthly returns | A held stock without a CRSP return keeps its last price (zero return), or earns the ratio to an observed price within three months; the next CRSP return applies when trading resumes |
| Terminal events | Audited terminal return is earned; remaining proceeds become cash until next rebalance |
| Execution | Idealized quarter-end marks; no within-day execution model; trading costs studied separately |

**Definition requiring reconciliation before calling this a replication:** the paper describes a payout measure using dividend yield
and the latest share count relative to a 24-month average. The precise dividend window, corporate-action treatment, and source fields
must be matched with the instructor's example or authors' methodology. This notebook explicitly implements the proxy above.
It does not replace payouts with dividend yield alone or claim cash buyback amounts are directly observed.

At formation month *t*, volatility uses *t−35,…,t*. Momentum uses *t−11,…,t−1*; the strategy earns returns from *t+1* onward.
For example, a December formation uses January–November momentum and first earns January's return.
Inputs observed only after month end must be lagged further. Same-close execution is a research simplification; daily implementation
would require a subsequent tradable price. Full-window eligibility and share-class treatment may create differences from the paper.
''')

code('''
from pathlib import Path
import json
import os
import platform
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

# Run from this notebook's folder, or from the parent project workspace.
BASE = Path.cwd()
if (BASE / "Final" / "conservative_formula_first_draft.ipynb").exists():
    BASE = BASE / "Final"
sys.path.insert(0, str(BASE))
from crsp_pipeline import config    # sample dates and portfolio sizes shared with the data pipeline
from research import engine         # selection, validation and backtest accounting

MODE = os.environ.get("CF_MODE", "demo")      # "demo" (default) or "crsp"
assert MODE in {"demo", "crsp"}, f"CF_MODE must be demo or crsp, got {MODE!r}"
SEED = 9897
N_UNIVERSE, N_HOLDINGS = config.UNIVERSE_SIZE, config.HOLDINGS
COST_BPS = 10                       # per dollar bought OR sold, scenario assumption
REAL_START = config.FIRST_INVESTMENT
DEMO_START = "2003-01-31"
CRSP_END = os.environ.get("CF_END", config.PAPER_END)    # last return month in CRSP mode
DATA = BASE / "data"
OUT = BASE / "output" / MODE
OUT.mkdir(parents=True, exist_ok=True)
LABEL = "SYNTHETIC DEMO — NOT EMPIRICAL EVIDENCE" if MODE == "demo" else "CRSP — DRAFT CONVENTIONS"
START = pd.Timestamp(DEMO_START if MODE == "demo" else REAL_START)
plt.rcParams.update({"figure.figsize": (11, 5), "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.alpha": .18,
                     "font.size": 10, "figure.dpi": 110})
pd.set_option("display.max_columns", 12)
display(Markdown(f"**Active data mode: {LABEL}** (set with the `CF_MODE` environment variable)"))
print({"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__})
''')

md(r'''
## 3. Real-data acquisition and required input schema
The notebook consumes a **normalized, audited extract**, not an arbitrary raw CRSP download. Access to a WRDS account is not
embedded here. Request the instructor's CRSP cleaning example, then obtain the monthly stock file, historical security names/type
information, share and price adjustment factors, cash distributions, terminal-event information, and monthly benchmark returns.

Save `data/crsp_monthly_normalized.parquet` with one row per security-month. The `crsp_pipeline` package
builds it from WRDS (`python -m crsp_pipeline all --user <wrds_username>`); see README.md.

| Column | Required meaning / units |
|---|---|
| `date`, `permno` | Calendar month-end and stable security identifier |
| `ret_total` | Decimal holding-period total return, including terminal-event effects exactly once |
| `ret_price` | Decimal price return excluding distributions; split adjusted |
| `price_adj` | Positive split-adjusted price; same share basis as `div_cash_adj` |
| `div_cash_adj` | Cash dividends per share during month on that basis; explicit 0 for verified no dividend, missing for unknown |
| `shares_adj` | Split-adjusted shares outstanding on a consistent basis through time, not raw shares across a split |
| `mktcap` | Observed security market cap in consistent currency units, normally abs(raw price) × raw shares |
| `eligible` | 1 if eligible for new positions at that date, otherwise 0; historical common-stock / exchange screens applied upstream |
| `is_exit` | 1 for an audited terminal observation after which proceeds become cash, otherwise 0 |
| `hist36` | 1 if the security has 36 calendar-consecutive non-missing total returns ending this month |
| `ret_hold`, `ret_hold_source` | Holding-period return used by the backtest and its source: `crsp` (equals `ret_total`), `price_ratio`, `stale_carry`, or `no_prior_row` (missing) |

Save `data/benchmark_monthly.csv` with `date`, `market_ret`, `rf`. Both return columns are monthly **decimal returns**,
not annual yields or percentage units. Prefer the CRSP value-weighted US market including dividends and a documented one-month
Treasury return series. An S&P 500 price index is not an equivalent benchmark.

**Preparation rules**
- Include inactive and delisted securities. Merge classifications using historical effective dates. Do not prefilter the full panel
  to today's eligible names; an ineligible held stock still needs its holding-period returns.
- Retain missing-return codes as missing until resolved; do not interpret CRSP special numeric codes as returns.
- Verify split adjustment direction against the installed CRSP field dictionary with a known split. Price, dividends, and shares
  must be consistent; a split must not appear as issuance. Cash dividends must exclude noncash stock distributions.
- Decide how multiple share classes map to firms; the current algorithm is security-level and may hold two classes unless the
  upstream eligibility rule chooses one at each date. Document this deviation or implement company aggregation.
- Reconcile legacy versus CIZ returns before any delisting merge. CIZ changes monthly return calculations and delisting conventions;
  do not mechanically append legacy delisting adjustments to an already adjusted series.
  See [CRSP's CIZ differences guide](https://www.crsp.org/wp-content/uploads/guides/CRSP_US_Stock_%26_Indexes_Databases_Summary_of_CIZ_Differences_to_Legacy_Files.pdf).
- Missing monthly returns of a held stock follow a disclosed stale-price convention rather than a silent fill. In a month
  without a CRSP return, the position keeps its last price (`stale_carry`, zero return), or earns the price ratio to its
  last price when CRSP reports a price in that month and the last price is at most three months old (`price_ratio`).
  When trading resumes, CRSP's return covers the gap, so a gap that ends within the holding quarter reproduces
  buy-and-hold. A gap that spans a rebalance loses the price change during the gap, and the position is traded at its
  last value; this affects 208 universe holding months in CRSP. Total returns, the history screen and all signals keep
  the missing value, and every case is counted in the audit tables. A held stock without any holding return stops the engine.
- The pipeline records the extract date, source tables and queries, row counts, conventions, code version, and file hashes
  in `data/manifest.json`, and writes the coverage, exclusion, missingness, missing-return, delisting, dividend and
  benchmark audits to `data/audit/`. CRSP licenses may constrain sharing; use the course-approved submission channel for
  the required data.

This adapter remains a data-preparation task for the empirical version. No live WRDS SQL is presented as tested or guaranteed.
''')

code('''
if MODE == "demo":
    panel, benchmark = engine.make_demo(seed=SEED)
else:
    panel = pd.read_parquet(config.PANEL_FILE)
    benchmark = pd.read_csv(config.BENCHMARK_FILE, parse_dates=["date"])
    # Nothing after the chosen end month enters the analysis.
    panel = panel.loc[panel.date.le(pd.Timestamp(CRSP_END))].reset_index(drop=True)
    benchmark = benchmark.loc[benchmark.date.le(pd.Timestamp(CRSP_END))]

panel, benchmark = engine.validate_inputs(panel, benchmark)
END = panel.date.max()
if MODE == "crsp":
    assert END == pd.Timestamp(CRSP_END), f"Panel ends {END.date()}, before the requested end {CRSP_END}"
display(Markdown(f"### Input audit — {LABEL}"))
display(pd.DataFrame({"value": [len(panel), panel.permno.nunique(),
    panel.date.min().date(), panel.date.max().date(), int(panel.is_exit.sum()),
    int(panel.ret_total.isna().sum())]},
    index=["security-month rows", "securities", "first month", "last month", "terminal rows", "missing total returns"]))
display(panel.ret_hold_source.value_counts().rename("holding-return source (rows)").to_frame())
display(panel.head())
''')

md(r'''
## 4. Signal construction
For a quarter-end formation date (t), the prototype defines

\[
\sigma_{i,t}=\sqrt{12}\,\operatorname{sd}(r_{i,t-35},\ldots,r_{i,t}),\qquad
M_{i,t}=\prod_{j=1}^{11}(1+r^{price}_{i,t-j})-1,
\]
\[
DY_{i,t}=\frac{\sum_{j=0}^{11}D^{adj}_{i,t-j}}{P^{adj}_{i,t}},\qquad
NPY^{proxy}_{i,t}=DY_{i,t}+1-\frac{S^{adj}_{i,t}}{\frac{1}{24}\sum_{j=0}^{23}S^{adj}_{i,t-j}}.
\]

Every window must consist of calendar-consecutive months with no missing input: a missing month invalidates the window
instead of allowing 36 observations spread over more than 36 months. No future observations are used or backfilled.
Missing dividends are not turned into zero, and missing shares are not carried forward without audit.
The signals are computed by the same vectorized function that the data pipeline audits use, and are attached to the
panel one-to-one on security and month, so every panel field (eligibility, history, holding returns) is kept alongside them.
''')

code('''
signals = engine.attach_signals(panel)
display(Markdown(f"### Latest signal snapshot — {LABEL}"))
display(signals.loc[signals.date.eq(signals.date.max()),
    ["date", "permno", "vol36", "momentum", "div_yield", "net_issuance", "npy"]].head(8).round(4))
''')

md(r'''
## 5. Portfolio construction and controlled comparisons
Selection at each quarter-end follows the order described in the paper. The history screen comes first: only eligible stocks
with 36 consecutive monthly returns qualify, and the universe is the largest 1,000 of them by market capitalization (all of
them when fewer exist, as before mid-1964). The universe is then split at the volatility median: the low-volatility pool
consists of the ⌊N/2⌋ members with the lowest 36-month volatility. Only after this partition are missing signals handled:
momentum and payout are ranked within the pool among members with both signals, and a member missing either cannot be
selected. Higher momentum and payout get smaller (better) ranks; the average rank determines selection, and ties in final
scores are broken by the stable security identifier. The engine stops if fewer complete members remain than holdings required.

The ablations keep the same universe, pool and complete-signal requirement, so a comparison changes the signal and not the
data availability. The low-volatility-only portfolio takes the lowest-volatility names of the universe directly. Counts of
eligible, history-eligible, universe, pool, missing-signal and selected names are recorded at every formation.

| Portfolio | Purpose |
|---|---|
| Conservative | Low-volatility half; best combined momentum and payout ranks |
| No momentum | Same low-volatility half; rank only payouts |
| No payout | Same low-volatility half; rank only momentum |
| No low-vol screen | Rank momentum and payouts across complete cases |
| Low volatility only | Lowest-volatility 100 complete cases |
| Universe equal weight | Equal-weight largest eligible stocks; measures the role of equal weighting |
| Universe cap weight | Capitalization-weight largest eligible stocks; same quarterly schedule |
| Market | External market total-return benchmark; not a reconstruction from today's stocks |

Sector constraints are a proposed follow-up, not part of the original baseline or this first implementation.
''')

code('''
STRATEGIES = engine.STRATEGIES
targets, audit_table = engine.formation_targets(signals, STRATEGIES, start=START, last=END,
                                                n_universe=N_UNIVERSE, n_hold=N_HOLDINGS)
count_cols = [c for c in engine.COUNT_FIELDS if c != "eligible_n"]
display(Markdown(f"### Formation counts by strategy (minimum and maximum) — {LABEL}"))
display(audit_table.groupby("strategy", sort=False)[count_cols].agg(["min", "max"]).T)
conservative_counts = audit_table.loc[audit_table.strategy.eq("Conservative")]
decade = (conservative_counts.formation.dt.year // 10 * 10).astype(str) + "s"
display(Markdown(f"### Conservative formation counts by decade (mean per formation) — {LABEL}"))
display(conservative_counts.groupby(decade)[engine.COUNT_FIELDS].mean().round(1))
''')

md(r'''
## 6. Monthly backtest with weight drift and transaction costs
The engine carries actual portfolio weights between quarter ends. It measures traded notional against these drifted weights,
including the initial purchase. Buying 100% of NAV costs one unit of traded notional; selling a full portfolio and buying a
disjoint one costs two. Reported **one-way turnover** is half this sum; costs use the full sum to avoid understating expenses.

For total traded stock notional (T_t=\sum_i|w^{target}_{i,t}-w^{pre}_{i,t}|) and per-dollar charge (c),
\[
1+R^{net}_{t+1}=(1-cT_t)(1+R^{gross}_{t+1}).
\]
This is a proportional NAV haircut approximation: target holdings are subsequently scaled to the remaining NAV.
It does not solve a fully self-financing execution optimization, model market impact, or charge terminal cash settlements as trades.
Cash earns the supplied monthly risk-free return. Terminal proceeds move to cash after the final return.
Holdings grow with the holding-period return of Section 3. A held position in a month without a CRSP return keeps its last
price or earns the observed price ratio, and these position-months are counted; a held position with no holding return at all
raises an exception rather than creating optimistic performance. At a rebalance during such a gap, the position is traded at
its last value.
''')

code('''
runs = {name: engine.backtest(panel, benchmark, target, START, END, COST_BPS) for name, target in targets.items()}
returns = pd.DataFrame({name: run.net for name, run in runs.items()})
returns["Market"] = benchmark.market_ret.reindex(returns.index)
assert not returns.isna().any().any()
print(f"{LABEL}: {len(returns)} investment months ({START.date()} to {END.date()}); "
      f"costs = {COST_BPS} bps per dollar traded.")
diagnostics = pd.DataFrame({name: {
    "months": len(run), "first_month": run.index.min().date(), "last_month": run.index.max().date(),
    "stale_position_months": int(run.stale_held_n.sum()), "stale_carry": int(run.stale_carry_n.sum()),
    "price_ratio": int(run.price_ratio_n.sum()), "max_stale_weight": run.stale_weight.max(),
    "all_cash_months": int(run.all_cash.sum()), "min_holdings": int(run.holdings_n.min()),
    "max_holdings": int(run.holdings_n.max())} for name, run in runs.items()}).T
display(Markdown(f"### Run diagnostics: calendar, positions without a CRSP return, all-cash months — {LABEL}"))
display(diagnostics)
''')

md(r'''
## 7. Accounting and timing checks
These checks test errors that can materially distort a trading backtest: accidentally using future data, failing to skip the
latest momentum month, disguising calendar gaps, ignoring portfolio drift, omitting trading costs, or dropping delisted holdings.
Each check builds a small synthetic example with a hand-computed answer and runs it through the same engine code as the
analysis above. The calendar checks confirm that a missing benchmark month, a late benchmark start, a missing formation
target, or a month without stock returns stops the backtest instead of shortening it silently. A second rebalance after
drift confirms that security-level trades equal the target minus the drifted weights, that traded notional and costs
reconcile, and that cash from a terminal exit is reinvested at the next rebalance.
Passing them establishes implementation behavior, not investment merit or exact agreement with the paper.
''')

code('''
from research import checks
check_results = pd.DataFrame({"check": [c.__name__.removeprefix("check_").replace("_", " ") for c in checks.ALL_CHECKS],
                              "what passed": checks.run_all()})
display(check_results)

# On the actual run: all targets are long-only and fully invested, and positive costs never raise a monthly return.
assert all(np.isclose(w.sum(), 1) and w.gt(0).all() for ts in targets.values() for w in ts.values())
assert all((run.net <= run.gross+1e-12).all() for run in runs.values())
print(f"PASS: {len(check_results)} fixture checks; target weights and cost ordering hold on the {MODE} run.")
''')

md(r'''
## 8. Performance report
CAGR uses compounded returns. Volatility and Sharpe use monthly observations with √12 scaling; Sharpe subtracts the aligned
monthly risk-free return. Maximum drawdown includes the initial wealth of 1, so a first-month loss is not omitted.
The market benchmark is gross of implementation fees; the constructed portfolios below pay the stated trading-cost scenario.
Sharpe estimates are descriptive and may be unreliable in short subperiods.
''')

code('''
def drawdown(r):
    wealth = (1+r).cumprod()
    return wealth/wealth.cummax().clip(lower=1)-1

def performance(r, rf):
    r = r.dropna()
    excess = r-rf.reindex(r.index)
    assert excess.notna().all()
    std = excess.std(ddof=1)
    return pd.Series({"Months": len(r), "CAGR": np.prod(1+r)**(12/len(r))-1,
        "Ann. volatility": r.std(ddof=1)*np.sqrt(12),
        "Sharpe": excess.mean()/std*np.sqrt(12) if std > 0 else np.nan,
        "Max drawdown": drawdown(r).min(), "Positive months": r.gt(0).mean()})

summary = pd.DataFrame({name: performance(returns[name], benchmark.rf) for name in returns}).T
summary["Ann. one-way turnover"] = pd.Series({name: run.one_way_turnover.mean()*12 for name,run in runs.items()})
display(Markdown(f"### Performance table — {LABEL}"))
display(summary.round(4))

shown = ["Conservative", "Low volatility only", "Universe equal weight", "Market"]
fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, layout="constrained")
for name in shown:
    wealth = (1+returns[name]).cumprod()
    wealth = pd.concat([pd.Series([1.], index=[returns.index[0]-pd.offsets.MonthEnd(1)]), wealth])
    axes[0].plot(wealth.index, wealth, label=name, lw=1.7)
    axes[1].plot(returns.index, drawdown(returns[name])*100, label=name, lw=1.3)
axes[0].set_yscale("log")
axes[0].set_ylabel("Growth of $1 (log scale)")
axes[0].legend(ncol=2, fontsize=9)
axes[1].set_ylabel("Drawdown (%)")
fig.suptitle(f"Conservative Formula | {LABEL}", fontsize=12)
fig.savefig(OUT / "wealth_and_drawdown.png", dpi=150)
plt.show()
''')

md(r'''
## 9. Extension A — what does each signal contribute?
Compare the full formula with the same portfolio size and rebalancing frequency after dropping one component. These are
controlled comparisons, not independent discoveries. A change in Sharpe alone is insufficient: check CAGR, drawdown, turnover,
and exposure changes. The low-volatility-only portfolio provides an additional simple reference.

The demo generator assigns no calibrated economic premium to these signals. Its relative performance is a property of artificial
data and random sampling, not an estimate of the value of momentum or payouts in US equities.
''')

code('''
ablation_names = STRATEGIES[:5]
ablation = summary.loc[ablation_names].copy()
ablation["CAGR minus full"] = ablation.CAGR-summary.loc["Conservative", "CAGR"]
display(Markdown(f"### Signal comparisons — {LABEL}"))
display(ablation.round(4))
fig, ax = plt.subplots(figsize=(10, 4), layout="constrained")
ax.barh(ablation_names, ablation.Sharpe, color=["#176B87"]+["#9CAFB7"]*4)
ax.set_xlabel("Annualized Sharpe ratio")
ax.set_title(f"Signal comparisons | {LABEL}", fontsize=11)
fig.savefig(OUT / "signal_comparisons.png", dpi=150)
plt.show()
''')

md(r'''
## 10. Extension B — performance through time
The intended empirical split is the original sample through December 2016, a separate 2017–2018 transition period, and a
post-publication evaluation from January 2019. January 2019 is chosen to exclude the 2018 publication year; it is not selected from
the returns. Use fixed rules across all periods. A historical post-publication sample is not a prospective untouched holdout for a
researcher working in 2026, so avoid overstating its independence.

The demonstration has only 2003 onward investable returns and cannot cover the original 1929–2016 sample.
Subperiod rows are reported only when at least 12 monthly observations exist, with actual coverage displayed.
''')

code('''
periods = {"Through 2016": (REAL_START, config.PAPER_END),
           "Transition 2017–2018": ("2017-01-01", "2018-12-31"),
           "Post-publication 2019+": ("2019-01-01", "2099-12-31")}
period_rows = []
for period, (lo, hi) in periods.items():
    for name in ["Conservative", "Market", "Low volatility only"]:
        r = returns.loc[lo:hi, name]
        if len(r) >= 12:
            row = performance(r, benchmark.rf).to_dict()
            period_rows.append({"period": period, "portfolio": name,
                "actual_start": str(r.index.min().date()), "actual_end": str(r.index.max().date()), **row})
subperiods = pd.DataFrame(period_rows)
display(Markdown(f"### Period analysis — {LABEL}"))
display(subperiods.round(4))
''')

md(r'''
## 11. Extension C — implementation costs
Use 0, 10, 25, and 50 basis points per dollar traded as **illustrative scenarios**, not measured historical costs.
The same positions are used in every scenario; no parameters are tuned to rescue the strategy.
The analysis omits taxes, financing, and nonlinear price impact. Since the strategy is long-only, stock-borrow fees are not modeled.
''')

code('''
cost_rows = []
for bps in [0, 10, 25, 50]:
    run = engine.backtest(panel, benchmark, targets["Conservative"], START, END, bps)
    row = performance(run.net, benchmark.rf).to_dict()
    cost_rows.append({"bps per dollar traded": bps,
                      "Ann. cost approximation": run.cost_fraction.mean()*12, **row})
cost_table = pd.DataFrame(cost_rows).set_index("bps per dollar traded")
display(Markdown(f"### Cost sensitivity — {LABEL}"))
display(cost_table.round(4))
assert cost_table.CAGR.is_monotonic_decreasing
fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
ax.plot(cost_table.index, cost_table.CAGR*100, marker="o", color="#176B87")
ax.set(xlabel="Cost per dollar traded (basis points)", ylabel="CAGR (%)",
       title=f"Trading-cost sensitivity | {LABEL}")
fig.savefig(OUT / "cost_sensitivity.png", dpi=150)
plt.show()
''')

md(r'''
## 12. Draft interpretation and limitations
**What is established now:** the notebook provides a reproducible selection rule, quarterly targets, monthly portfolio accounting,
weight drift, cash settlement handling, diagnostic tables, and a fixed set of comparisons. The tests check several consequential
implementation errors. The saved demo results establish only that this pipeline executes.

**What is not established:** whether the strategy outperforms, whether the published results can be reproduced, whether its alpha
survives factor controls, or whether it remains practical after real trading frictions. No empirical conclusion can be drawn from
the synthetic charts. The demo is a fixed-universe simulation; terminal-event accounting is tested separately with a toy example.

When real data are available, the discussion should answer:
1. How closely do the sample, signal conventions, gross returns, volatility, and drawdowns match the paper?
2. Does the full formula beat equal-weight and capitalization-weight universe controls, or is weighting driving the result?
3. Which omitted signal changes outcomes most, and is the result stable after costs and in later periods?
4. Are the findings concentrated in certain sectors, stock sizes, or unusually favorable decades?
5. Which discrepancies reflect database revisions, historical eligibility, terminal events, payout definitions, or implementation?

**Inference remains future work.** For the empirical draft, estimate market beta and factor-model alpha using aligned factor data
and heteroskedasticity/autocorrelation-robust standard errors. A paired block bootstrap can quantify uncertainty in strategy
differences while preserving serial dependence. Do not report a positive average return or a higher sample Sharpe as statistical
significance. Multiple extensions increase the chance of finding a favorable result by luck.

### First-draft conclusion
The Conservative Formula is a tractable research topic because its economic story maps to transparent portfolio rules and
testable component comparisons. This draft implements that research design. The central investment question remains unanswered
pending an audited historical equity dataset and reconciliation of the payout construction. The empirical version should preserve
these baseline rules, disclose deviations, and report unfavorable findings as carefully as favorable ones.
''')

md(r'''
## 13. Export results and next submission milestones
Exports carry the mode in both their folder and filenames. The notebook is self-contained in demo mode; its generator and the
executed outputs can be archived with it. For the final course submission, include the actual required data and any helper files
so the notebook can run from beginning to end in the approved environment.

**Before an empirical first submission**
- Confirm Project 8 availability and the team roster under the course's first-come-first-served policy.
- Obtain the instructor's CRSP example and audit the normalization against several stocks, a split, an issuance, and a delisting.
- Confirm the payout proxy, stock/company universe convention, pre-1929 warm-up, and benchmark mapping.
- Replace demo inputs, rerun all cells, investigate failures rather than bypassing them, and replace the draft discussion with actual findings.
- Add factor attribution and uncertainty estimates if time permits. A sector-constraint extension is optional and should follow a clean baseline.

The final deliverable should distinguish replication results from extensions and explain every departure from the paper.
''')

code('''
prefix = "synthetic_demo" if MODE == "demo" else "crsp_draft"
summary.to_csv(OUT / f"{prefix}_performance.csv")
returns.to_csv(OUT / f"{prefix}_monthly_returns.csv")
audit_table.to_csv(OUT / f"{prefix}_formation_audit.csv", index=False)
diagnostics.to_csv(OUT / f"{prefix}_run_diagnostics.csv", index_label="strategy")
subperiods.to_csv(OUT / f"{prefix}_subperiods.csv", index=False)
cost_table.to_csv(OUT / f"{prefix}_cost_sensitivity.csv")
manifest = {"mode": MODE, "label": LABEL, "seed": SEED if MODE == "demo" else None,
    "universe_cap": N_UNIVERSE, "holdings": N_HOLDINGS, "cost_bps": COST_BPS,
    "first_return": str(returns.index.min().date()), "last_return": str(returns.index.max().date()),
    "payout_definition": "Trailing 12m cash dividend yield + 1 - shares / trailing 24m mean shares",
    "status": "Demonstration only" if MODE == "demo" else "Normalized CRSP input; draft conventions require audit",
    "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}
(OUT / f"{prefix}_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"Saved {prefix} tables, charts, and manifest to {OUT}")
print("No real equity performance has been established." if MODE == "demo" else
      "Review provenance and replication deviations before drawing conclusions.")
''')

md(r'''
## References and source notes
1. Van Vliet, P., and Blitz, D. (2018). *The Conservative Formula: Quantitative Investing Made Easy*.
   [SSRN working-paper record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152).
   The working-paper and journal versions use different author ordering. Use a single version consistently in the final bibliography.
2. Robeco (2023). *The Introductory Guide to Conservative Investing*.
   [Guide and further reading](https://www.robeco.com/docm/docu-202302-guide-to-conservative-investing.pdf).
   This provides accessible context and references on low-risk investing; it is also a manager publication, not independent validation.
3. CRSP. *Summary of CIZ Differences to Legacy Files*.
   [Database methodology](https://www.crsp.org/wp-content/uploads/guides/CRSP_US_Stock_%26_Indexes_Databases_Summary_of_CIZ_Differences_to_Legacy_Files.pdf).
   Record the database version actually used in the empirical study.
4. MTH 9897. *Final Projects 2026*, provided course brief, pages 1 and 5: submission requirements and Project 8.

**Further literature to read, not results replicated here:** the paper's references on the low-volatility effect, momentum, and
shareholder payouts are natural starting points for expanding the literature review. Read the originals before attributing specific
mechanisms or numerical findings to them.

**Reproducibility note:** demonstration data are generated by `make_demo` using the fixed seed above. They are artificial and not
derived from CRSP. No live trading, external submission, or upload occurs when running this notebook.
''')

nb = nbf.v4.new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12"},
})
nbf.validate(nb)
path = ROOT / "conservative_formula_first_draft.ipynb"
nbf.write(nb, path)
print(f"Created {path}: {len(cells)} cells")
