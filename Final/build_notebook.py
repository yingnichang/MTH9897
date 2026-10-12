"""Build the report notebook: a critical replication of the Conservative Formula on CRSP, 1929-2024.

Every result shown is read from the tracked result contract (`results/`, written by `python -m research.run_all`)
through the hash-checked loader; prose numbers are formatted from `research.summary.numbers()`.
Run `python build_notebook.py && python execute_notebook.py`.
"""
from pathlib import Path
from textwrap import dedent

import nbformat as nbf

ROOT = Path(__file__).resolve().parent
NOTEBOOK = "conservative_formula_first_draft.ipynb"
cells = []


def md(s):
    cells.append(nbf.v4.new_markdown_cell(dedent(s).strip()))


def code(s):
    cells.append(nbf.v4.new_code_cell(dedent(s).strip()))


md(r'''
# The Conservative Formula: A Critical Replication on CRSP, 1929–2024
**MTH 9897 Systematic Trading · Project 8 · Final report**
**Authors:** [Add names and team number]

**Paper:** David Blitz and Pim van Vliet (2018), "The Conservative Formula: Quantitative Investing Made Easy",
*The Journal of Portfolio Management* 44(7); working paper [SSRN 3145152](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152).

This report replicates the paper's US results on CRSP over its own sample, 1929–2016, and then asks three questions
that were fixed before any post-2016 return was computed: is the formula's return explained by known factors, has
its performance decayed, and how much of it survives realistic trading costs? The headline period is 1990–2024.
''')

code(r'''
from pathlib import Path
import os
import platform
import subprocess
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import Image, Markdown, display

BASE = Path.cwd()
if (BASE / "Final" / "build_notebook.py").exists():          # opened from the parent folder
    BASE = BASE / "Final"
sys.path.insert(0, str(BASE))
from research import results
from research import summary as S
from research.summary import ci, ci_num, num, pct, pp

MODE = os.environ.get("CF_MODE", "crsp")                     # "crsp" (default): empirical; "demo": synthetic only
assert MODE in {"crsp", "demo"}, f"CF_MODE must be crsp or demo, got {MODE!r}"
RESULTS = BASE / "results"
if MODE == "crsp" and os.environ.get("CF_RECOMPUTE") == "1":   # recompute every study from data/ first
    subprocess.run([sys.executable, "-m", "research.run_all"], cwd=BASE, check=True)
EMPIRICAL = MODE == "crsp"
N = S.numbers(RESULTS) if EMPIRICAL else {}
pd.set_option("display.max_columns", 30, "display.width", 200)


def empirical():
    """True in CRSP mode; in demo mode, say that the empirical section is not shown."""
    if not EMPIRICAL:
        display(Markdown("*Empirical section: shown only in CRSP mode (`CF_MODE=crsp`). This run is a synthetic demonstration.*"))
    return EMPIRICAL


def R(study, name, **kw):
    """A result table from results/, verified against results/manifest.json."""
    return results.load(study, name, root=RESULTS, **kw)[0]


def figure(study, name, width=900):
    display(Image(filename=str(results.path(study, name, root=RESULTS)), width=width))


def say(text):
    display(Markdown(text))


def table(df, pcts=(), nums=(), digits=1, ndigits=2):
    """Format decimal-return columns as percentages and others as numbers (display only)."""
    out = df.copy()
    for c in pcts:
        out[c] = out[c].map(lambda x: "" if pd.isna(x) else pct(x, digits))
    for c in nums:
        out[c] = out[c].map(lambda x: "" if pd.isna(x) else num(x, ndigits))
    return out


say(f"**Data mode: {'CRSP (empirical results from results/)' if EMPIRICAL else 'SYNTHETIC DEMONSTRATION — not empirical evidence'}**")
''')

code(r'''
if empirical():
    h = "1990–2024|net30"
    say(f"""### Abstract
On CRSP over the paper's sample (1929–2016), our Conservative portfolio earns {pct(N['rep_cons_compounded'])} a year
compounded, gross of costs, with {pct(N['rep_cons_volatility'])} volatility (the paper reports {pct(N['paper_cons_compounded'])} and
{pct(N['paper_cons_volatility'])}); the CRSP value-weighted market earns {pct(N['rep_mkt_compounded'])}. The return is largely a bundle of
known premia: the Carhart alpha of the long-short contrast (Conservative minus Speculative) is {pct(N['att_cms_carhart_alpha'])}
against the paper's {pct(N['t2_a_carhart_paper'])}, and over 1963–2016 the Conservative portfolio's alpha on the five Fama–French factors
plus momentum is {pct(N['att_cons_ff5umd_alpha'], 2)} (NW t {num(N['att_cons_ff5umd_t'])}).
Performance has decayed: the Carhart alpha falls from {pct(N['ct_alpha|1929–1962|gross'])} (1929–1962) to {pct(N['ct_alpha|1990–2016|gross'])}
(1990–2016) and {pct(N['ct_alpha|2017–2024|gross'])} (2017–2024, only {N['ct_months|2017–2024']} months). In the headline period 1990–2024,
net of 30 bps per dollar traded, the excess return over the market is {pct(N['ct_excess|' + h])} {ci(N['ct_excess_lo|' + h], N['ct_excess_hi|' + h])}
and the Carhart alpha {pct(N['ct_alpha|' + h], 2)} {ci(N['ct_alpha_lo|' + h], N['ct_alpha_hi|' + h])}; the alpha's break-even cost is
{N['be_alpha|1990–2024']:.0f} bps. The evidence therefore does not show that the formula beats the market on recent data once known
factors and costs are taken into account; it is an inexpensive way to hold the low-volatility, momentum and payout premia.""")
''')

md(r'''
## 1. Question, paper and test design
The paper proposes a simple rule: among the 1,000 largest US stocks, keep the half with the lowest 36-month
volatility, rank them on 12-1 momentum and net payout yield (NPY), and hold the best 100 equally weighted, rebalanced
quarterly. It reports a high return with low risk over 1929–2016 and a large alpha for the contrast between this
"Conservative" portfolio and its "Speculative" mirror image.

A replication alone cannot say whether the rule still works. The report therefore treats the 1929–2016 replication as
a benchmark and then answers three questions, whose tests and periods were fixed before any 2017–2024 return was
computed:
1. **Known factors.** Is the return explained by the Carhart four factors (primary) or the five Fama–French factors
   plus momentum (robustness)? CAPM alphas are shown only for comparison with the paper.
2. **Decay.** Every headline statistic is reported for 1929–1962, 1963–1989, 1990–2016 and 2017–2024, together with
   rolling 120-month windows. The headline period is **1990–2024**; 2017–2024 is post-sample and short.
3. **Costs.** Net returns at 10 and 30 bps per dollar traded, and the break-even cost at which the excess return or
   the alpha disappears.
In the critical tests, compounded and arithmetic returns, volatilities and Sharpe ratios carry 12-month block-bootstrap
95% intervals, and excess returns and alphas Newey–West (12 lags) 95% intervals; maximum drawdown is a path statistic
and is reported without an interval. Elsewhere the report gives Newey–West t-statistics, and intervals where it states
them. The course diagnostics, portfolio-construction extensions and one declared improvement follow; each is labeled as an extension and leaves the baseline unchanged.
''')

md(r'''
## 2. Data
The data are the CRSP monthly stock file (legacy format) for US common stocks (share codes 10 and 11) on NYSE, AMEX
and NASDAQ, with security names, delistings, distributions and the CRSP index file, extracted from WRDS, plus the
Fama–French factors. A pipeline (`crsp_pipeline`) normalizes them to one row per security-month and writes the audit
tables below. Conventions that the paper leaves open are fixed and disclosed:

| Item | Convention |
|---|---|
| Universe | Eligible common stocks with 36 consecutive monthly returns; the largest 1,000 by security market cap (all of them while fewer exist, before mid-1964) |
| Share classes | One class per company: the largest common-stock class |
| Dividends | Implied from total minus price return (legacy `retx` includes special distributions) |
| Delistings | CRSP delisting returns; missing performance delistings imputed at −30% (NYSE/AMEX) or −55% (NASDAQ) |
| Missing monthly returns of held stocks | Stale-price carry (zero return), or the price ratio to the last price when CRSP reports a price within three months; CRSP's return applies when trading resumes |
| Benchmark and risk-free rate | CRSP value-weighted index including distributions; Fama–French one-month T-bill |
''')

code(r'''
if empirical():
    ex = R("data_audit", "extract_summary.json")
    s = ex["sample"]
    say(f"""Extracted from `{ex['host']}` at {ex['extracted_at_utc']} (UTC), months {ex['start']} to {ex['end']}:
{s['panel_rows']:,} security-months of {s['securities']:,} securities, {s['terminal_rows']:,} terminal events
(delisting returns observed for {s['delist_sources']['observed']:,}, imputed for {s['delist_sources']['imputed_shumway']},
missing and set to zero for {s['delist_sources']['missing_set_zero']}). The first formation (December 1928) has a universe of
{s['first_formation_universe_n']} stocks; the full 1,000 is first reached in {s['first_formation_with_full_universe'][:7]}.
WRDS exposes no release identifier, so the extract is identified by its time stamp and file hashes.""")
    cov = R("data_audit", "formation_coverage.csv", parse_dates=["date"])
    cov["decade"] = (cov["date"].dt.year // 10 * 10).astype(str) + "s"
    display(Markdown("**Universe coverage at quarter-end formations (mean by decade)**"))
    display(cov.groupby("decade")[["eligible_n", "eligible_hist36_n", "universe_n"]].mean().round(0).astype(int))
    mr = R("data_audit", "missing_returns.csv").set_index("decade")
    display(Markdown("**Missing monthly returns: panel rows and universe holding months, by decade**"))
    display(mr[["nan_ret_rows", "stale_carry_rows", "price_ratio_rows", "universe_holding_months",
                "universe_holding_stale_carry", "universe_holding_price_ratio"]])
    dv = R("data_audit", "dividend_reconciliation.csv").set_index("decade")
    bc = R("data_audit", "benchmark_check.csv").set_index("decade")
    display(Markdown("**Implied dividends against CRSP distributions, and the CRSP VW index against the Fama–French market**"))
    display(pd.concat([dv[["agree_ordinary_cash"]].map(lambda x: pct(x)),
                       bc[["corr_crsp_vw_vs_ff_market"]].round(4)], axis=1))
''')

md(r'''
## 3. Baseline rule and deviations from the paper
At each quarter end the engine applies the paper's order: the history screen, then the 1,000 largest by market cap,
then the low-volatility half (⌊N/2⌋ names), and only then the momentum and NPY ranks among pool members with both
signals; the best 100 by average rank are held equally weighted. Weights drift with returns between rebalances; a
delisted holding earns its delisting return and becomes cash until the next rebalance. Costs are a proportional charge
per dollar traded against the drifted weights. The Speculative portfolio takes the high-volatility half and the 100
weakest combined scores; the standalone controls hold the 100 best names on a single signal; "Small" holds the 100
smallest members of the universe. The paper's Value control (book-to-market) is excluded because the CRSP-only extract
has no book equity, and Table 2's panels C and D are excluded because the q-factors and the AQR QMJ and BAB factors are
not in our sources.
''')

code(r'''
if empirical():
    display(Markdown("**Documented deviations from the paper's method**"))
    display(R("replication", "deviations.csv").set_index("item"))
''')

md(r'''
## 4. Replication, 1929–2016
The comparison uses the paper's own definitions (Table 1): simple return = 12 × mean monthly return; compounded
return; volatility = √12 × monthly standard deviation; the paper's "Sharpe" = simple return / volatility (no T-bill is
subtracted, despite its caption); de-risking factor = 16.5% / volatility; and return at the same risk =
rf + (simple − rf) × 16.5% / volatility. All returns are gross of costs.
''')

code(r'''
if empirical():
    t1 = R("paper_targets", "table1_vs_paper.csv")
    ratio = t1["row"].isin(["De-risking factor", "Sharpe (simple)"])
    t1["cell"] = np.where(t1["status"].ne("compared"), np.where(ratio, t1["paper"].map(lambda x: num(x)),
                                                                t1["paper"].map(lambda x: pct(x))) + " / excluded",
                 np.where(ratio, t1["paper"].map(lambda x: num(x)) + " / " + t1["ours"].map(lambda x: num(x)),
                          t1["paper"].map(lambda x: pct(x)) + " / " + t1["ours"].map(lambda x: pct(x))))
    display(Markdown("**Table 1, paper / ours (gross, 1929–2016)**"))
    display(t1.pivot(index="row", columns="column", values="cell").loc[t1["row"].unique(),
            ["Formula", "Market", "Small", "Value", "Momentum", "Lowvol", "NPY"]])
    say(f"""The replication is close on return and risk: Conservative compounds at {pct(N['rep_cons_compounded'], 2)} with
{pct(N['rep_cons_volatility'], 2)} volatility (paper {pct(N['paper_cons_compounded'])}, {pct(N['paper_cons_volatility'])}), and the market at
{pct(N['rep_mkt_compounded'], 2)} with {pct(N['rep_mkt_volatility'], 2)} ({pct(N['paper_mkt_compounded'])}, {pct(N['paper_mkt_volatility'])}).
The Speculative portfolio compounds at only {pct(N['rep_spec_compounded'], 2)} with {pct(N['rep_spec_volatility'])} volatility.
Conservative beats the market in {N['decades_cons_beats_mkt']} of {N['decades_n']} decade buckets (partial decades labeled).
The largest gap is Small's simple return ({pct(N['t1_small_simple'])} against {pct(N['paper_small_simple'])}); its compounded return
is within one percentage point. Explanations of every gap above the declared thresholds are listed below.""")
    figure("replication", "fig3.png")
    figure("replication", "fig4.png")
    gaps = R("paper_targets", "gaps.csv")
    display(Markdown("**Gaps above 1 pp (returns, alphas) or 5 pp (turnover), with explanations**"))
    display(table(gaps[["table", "item", "paper", "ours", "difference", "explanation"]], pcts=["paper", "ours", "difference"]))
''')

md(r'''
## 5. Factor attribution (Table 2) and trading costs (Table 4)
The contrast CMS = R(Conservative) − R(Speculative) is a zero-investment return, regressed on the factors without
subtracting the risk-free rate. Net of costs, both legs pay their trading costs (no borrow or financing cost). Alphas
are annualized; the paper's t-values are compared with our OLS t-statistics, with Newey–West t-statistics alongside.
Panel B uses the five-factor file's own market and size factors.
''')

code(r'''
if empirical():
    t2 = R("paper_targets", "table2_vs_paper.csv")
    t2 = t2.loc[t2["term"].ne("adj. R2")]
    display(Markdown("**Table 2, CMS: paper against ours (gross)**"))
    show = t2[["panel", "model", "sample", "n", "term", "paper", "paper_t", "ours", "ours_t_ols", "ours_t_nw", "status"]].copy()
    show["n"] = show["n"].map(lambda x: "" if pd.isna(x) else f"{int(x)}")
    alpha = show["term"].eq("alpha (annual)")
    for c in ["paper", "ours"]:
        show[c] = np.where(alpha, show[c].map(lambda x: "" if pd.isna(x) else pct(x, 2)), show[c].map(lambda x: "" if pd.isna(x) else num(x)))
    display(table(show, nums=["paper_t", "ours_t_ols", "ours_t_nw"]).fillna(""))
    say(f"""Over 1963–2016 (panel B, N = {N['t2_b_capm_n']}) the CMS alphas reproduce the paper almost exactly: CAPM
{pct(N['t2_b_capm_ours'], 2)} against {pct(N['t2_b_capm_paper'])}, FF3 {pct(N['t2_b_ff3_ours'], 2)} against {pct(N['t2_b_ff3_paper'])},
FF5 {pct(N['t2_b_ff5_ours'], 2)} against {pct(N['t2_b_ff5_paper'])} and FF5 plus momentum {pct(N['t2_b_ff5mom_ours'], 2)} against
{pct(N['t2_b_ff5mom_paper'])}. Over 1929–2016 (panel A) our CAPM and Carhart alphas, {pct(N['t2_a_capm_ours'], 2)} and
{pct(N['t2_a_carhart_ours'], 2)}, are below the paper's {pct(N['t2_a_capm_paper'])} and {pct(N['t2_a_carhart_paper'])}, so the gap sits in the
pre-1963 period, where our universe is smaller. For the long-only Conservative portfolio the Carhart alpha is
{pct(N['att_cons_carhart_alpha'], 2)} (NW t {num(N['att_cons_carhart_t'])}), and over 1963–2016 the five factors plus momentum leave
{pct(N['att_cons_ff5umd_alpha'], 2)} (t {num(N['att_cons_ff5umd_t'])}): profitability and investment explain the rest. Net of 30 bps
with both legs paying, the CMS Carhart alpha is {pct(N['att_cms_carhart_net30_alpha'], 2)} (t {num(N['att_cms_carhart_net30_t'])}).""")
    t4 = R("paper_targets", "table4_vs_paper.csv")
    display(Markdown("**Table 4, costs = turnover × 8 × cost per dollar (paper; ours on compounded and arithmetic gross bases)**"))
    t4w = t4.pivot(index="row", columns="our_gross_basis", values="ours").loc[t4["row"].unique()]
    t4w.insert(0, "paper", t4.drop_duplicates("row").set_index("row")["paper"])
    display(t4w.map(lambda x: pct(x, 2)))
    td = R("replication", "turnover_decomposition.csv").set_index("era")
    say(f"""One-way quarterly turnover is {pct(N['rep_turnover'])} against the paper's {pct(N['paper_turnover'], 0)}. The decomposition
below shows that it is almost entirely name replacement and that it is higher after 1964, so the smaller early universe
does not explain it; the paper does not state how its turnover is measured. At the paper's cost levels the cost drag is
small: net of 30 bps Conservative compounds at {pct(N['rep_cons_net30_compounded'], 2)}.""")
    display(table(td, pcts=["one_way", "bought_new_names", "sold_dropped_names", "reweight_kept_names", "cash_reinvested"],
                  nums=["names_replaced"], ndigits=1))
''')

md(r'''
## 6. Critical tests: known factors, decay and costs, 1929–2024
The rules and periods below were fixed before any 2017–2024 return was computed; the time stamp of the first load of
post-2016 data is printed from the run record. The 1929–2016 part of the extended run is bit-identical to the
replication. Excess returns over the market and alphas are arithmetic annual figures with Newey–West (12 lags) 95%
intervals; compounded returns, volatilities and Sharpe ratios carry 12-month block-bootstrap 95% intervals (5,000
draws). Maximum drawdown is a path statistic and has no interval.
''')

code(r'''
if empirical():
    say(f"First load of 2017–2024 data: **{N['freeze_utc']}** (UTC), after the rules were frozen.")
    sp = R("critical_tests", "subperiods.csv")
    c = sp.loc[sp["portfolio"].eq("Conservative") & sp["returns"].isin(["gross", "net30"])].copy()
    for col in ("compounded", "volatility"):
        c[f"{col} [95% CI]"] = [f"{pct(a)} {ci(lo, hi)}" for a, lo, hi in zip(c[col], c[f"{col}_ci95_low"], c[f"{col}_ci95_high"])]
    for col, label in [("sharpe_paper", "Sharpe (paper)"), ("sharpe_excess", "Sharpe (excess)")]:
        c[f"{label} [95% CI]"] = [f"{num(a)} {ci_num(lo, hi)}" for a, lo, hi in zip(c[col], c[f"{col}_ci95_low"], c[f"{col}_ci95_high"])]
    c["excess [95% CI]"] = [f"{pct(a, 2)} {ci(lo, hi)}" for a, lo, hi in zip(c.excess_vs_market, c.excess_ci95_low, c.excess_ci95_high)]
    c["Carhart alpha (NW t) [95% CI]"] = [f"{pct(a, 2)} ({num(t)}) {ci(lo, hi)}" for a, t, lo, hi in
                                          zip(c.carhart_alpha, c.carhart_t_nw, c.carhart_ci95_low, c.carhart_ci95_high)]
    c["FF5+UMD alpha (NW t) [95% CI]"] = [("" if pd.isna(a) else f"{pct(a, 2)} ({num(t)}) {ci(lo, hi)}") for a, t, lo, hi in
                                          zip(c.ff5umd_alpha, c.ff5umd_t_nw, c.ff5umd_ci95_low, c.ff5umd_ci95_high)]
    c["max drawdown (path, no CI)"] = c["max_drawdown"].map(pct)
    display(Markdown("**Conservative by fixed period: gross and net of 30 bps** (Sharpe (paper) = arithmetic return / volatility; "
                     "Sharpe (excess) subtracts the T-bill; FF5+UMD alphas start in 1963)"))
    display(c.set_index(["period", "returns"])[["months", "compounded [95% CI]", "volatility [95% CI]", "Sharpe (paper) [95% CI]",
            "Sharpe (excess) [95% CI]", "excess [95% CI]", "Carhart alpha (NW t) [95% CI]", "FF5+UMD alpha (NW t) [95% CI]",
            "max drawdown (path, no CI)"]])
    figure("critical_tests", "fig_rolling.png")
    be = R("critical_tests", "breakeven.csv")
    be["break-even (bps per dollar traded)"] = [f"{b:.0f}" if s == "found" else s.replace("<= 0", "none: gross value ≤ 0")
                                                for b, s in zip(be.breakeven_bps, be.status)]
    display(Markdown("**Break-even cost of Conservative by period**"))
    display(be.pivot(index="period", columns="measure", values="break-even (bps per dollar traded)").assign(
        one_way_turnover_per_quarter=be.groupby("period")["one_way_turnover_per_quarter"].first().map(pct)))
    h, g = "1990–2024|net30", "1990–2024|gross"
    say(f"""**Headline, 1990–2024.** Gross of costs, Conservative's excess return over the market is {pct(N['ct_excess|' + g], 2)}
{ci(N['ct_excess_lo|' + g], N['ct_excess_hi|' + g])} and its Carhart alpha {pct(N['ct_alpha|' + g], 2)} (t {num(N['ct_alpha_t|' + g])})
{ci(N['ct_alpha_lo|' + g], N['ct_alpha_hi|' + g])}. Net of 30 bps the excess return is {pct(N['ct_excess|' + h], 2)}
{ci(N['ct_excess_lo|' + h], N['ct_excess_hi|' + h])} and the alpha {pct(N['ct_alpha|' + h], 2)} (t {num(N['ct_alpha_t|' + h])})
{ci(N['ct_alpha_lo|' + h], N['ct_alpha_hi|' + h])}; the five factors plus momentum give {pct(N['ct_ff5_alpha|' + h], 2)}
(t {num(N['ct_ff5_t|' + h])}) {ci(N['ct_ff5_alpha_lo|' + h], N['ct_ff5_alpha_hi|' + h], 2)}, which is
{S.significance(N['ct_ff5_alpha_lo|' + h], N['ct_ff5_alpha_hi|' + h])}. The break-even cost is {N['be_excess|1990–2024']:.0f} bps for the
excess return and {N['be_alpha|1990–2024']:.0f} bps for the alpha, at {pct(N['be_turnover|1990–2024'])} one-way turnover a quarter.
Conservative still compounded at {pct(N['ct_comp|' + g])} {ci(N['ct_comp_lo|' + g], N['ct_comp_hi|' + g])} gross
({pct(N['ct_comp|' + h])} {ci(N['ct_comp_lo|' + h], N['ct_comp_hi|' + h])} net of 30 bps) with {pct(N['ct_vol|' + g])}
{ci(N['ct_vol_lo|' + g], N['ct_vol_hi|' + g])} volatility, against the market's {pct(N['ct_mkt_compounded|1990–2024'])}
{ci(N['ct_mkt_comp_lo|1990–2024'], N['ct_mkt_comp_hi|1990–2024'])} and {pct(N['ct_mkt_vol|1990–2024'])}
{ci(N['ct_mkt_vol_lo|1990–2024'], N['ct_mkt_vol_hi|1990–2024'])}; its Sharpe ratio is {num(N['ct_sharpe|' + g])}
{ci_num(N['ct_sharpe_lo|' + g], N['ct_sharpe_hi|' + g])} gross (paper definition; {num(N['ct_sharpe_x|' + g])}
{ci_num(N['ct_sharpe_x_lo|' + g], N['ct_sharpe_x_hi|' + g])} over the T-bill). The edge is mainly lower risk, not higher return.
The cost-inclusive CMS keeps a Carhart alpha of {pct(N['ct_cms_net30_alpha|1990–2024'], 2)} (t {num(N['ct_cms_net30_t|1990–2024'])})
{ci(N['ct_cms_net30_lo|1990–2024'], N['ct_cms_net30_hi|1990–2024'])}.

**Decay.** The gross Carhart alpha is {pct(N['ct_alpha|1929–1962|gross'], 2)} (t {num(N['ct_alpha_t|1929–1962|gross'])}) in 1929–1962,
{pct(N['ct_alpha|1963–1989|gross'], 2)} (t {num(N['ct_alpha_t|1963–1989|gross'])}) in 1963–1989, {pct(N['ct_alpha|1990–2016|gross'], 2)}
(t {num(N['ct_alpha_t|1990–2016|gross'])}) in 1990–2016 and {pct(N['ct_alpha|2017–2024|gross'], 2)} (t {num(N['ct_alpha_t|2017–2024|gross'])})
in 2017–2024. **The 2017–2024 period has only {N['ct_months|2017–2024']} months:** its interval
{ci(N['ct_alpha_lo|2017–2024|gross'], N['ct_alpha_hi|2017–2024|gross'])} includes sizable positive values, so it shows no evidence of
outperformance rather than proof of failure. Early-period break-even costs are high, but so were the actual trading costs of that era,
which were well above 30 bps.""")
''')

md(r'''
## 7. Signal diagnostics
These diagnostics study the three signals, not the paper's two-stage selection. Each signal is computed in the monthly
universe, demeaned within Fama–French 12 industries, standardized by its cross-sectional standard deviation and clipped
to ±3; the composite is the equal-weight mean of the three neutralized exposures. (The composite factor-mimicking
portfolio below is a different object: the sum of the three unit-exposure signal portfolios, which has unit exposure to
each signal.) Forward returns are industry-adjusted and include delisting returns. The
information coefficient (IC) is the rank correlation of exposure and forward return; "mean/sd" is the literal ratio,
reported apart from the Newey–West t-statistic (lags h − 1 + 12). Factor-mimicking portfolios come from monthly
cross-sectional weighted least squares on the exposures, size and industry dummies; they are gross, levered paper
portfolios, not investable as they stand.
''')

code(r'''
if empirical():
    ic = R("diagnostics", "ic.csv")
    ic["IC: mean (mean/sd; NW t)"] = [f"{num(m, 3)} ({num(r)}; {num(t, 1)})" for m, r, t in zip(ic["mean"], ic.mean_over_sd_literal, ic.t_nw)]
    display(Markdown("**Rank IC by horizon h (months)**"))
    display(ic.pivot(index="exposure", columns="h", values="IC: mean (mean/sd; NW t)"))
    figure("diagnostics", "fig_ic_ma.png")
    figure("diagnostics", "fig_decay.png")
    ds = R("diagnostics", "deciles_subperiods.csv")
    ds = ds.loc[ds["h"].eq(1) & ds["decile"].eq("D10-D1")]
    ds["D10−D1 (NW t)"] = [f"{pct(m, 2)} ({num(t)})" for m, t in zip(ds.mean_er, ds.t_nw)]
    display(Markdown("**Top-minus-bottom decile spread of industry-adjusted 1-month returns, by period**"))
    display(ds.pivot(index="exposure", columns="sample", values="D10−D1 (NW t)"))
    figure("diagnostics", "fig_deciles.png")
    say(f"""The composite's 1-month IC is {num(N['ic_comp_h1'], 3)} (NW t {num(N['ic_comp_h1_t'], 1)}). Its decile spread is concentrated
in 1963–2016: {pct(N['dec_comp_spread|1963–1989'], 2)} (t {num(N['dec_comp_t|1963–1989'])}) in 1963–1989 and
{pct(N['dec_comp_spread|1990–2016'], 2)} (t {num(N['dec_comp_t|1990–2016'])}) in 1990–2016, against {pct(N['dec_comp_spread|1929–1962'], 2)}
before 1963 and {pct(N['dec_comp_spread|2017–2024'], 2)} (t {num(N['dec_comp_t|2017–2024'])}) in 2017–2024. Low volatility has a
positive rank IC but a flat mean spread, because the high-volatility deciles are strongly right-skewed: rank and mean
measures answer different questions.""")
    pm = R("fmp", "paper_metrics.csv")
    pm = pm.loc[pm["period"].isin(["1929–2024", "2017–2024"])]
    display(Markdown("**Lagged composite factor-mimicking paper portfolio (active over CRSP VW, gross)**"))
    display(table(pm[["K", "weighting", "period", "mean_annual", "vol_annual", "ir", "max_drawdown_active", "skew",
                      "excess_kurtosis", "corr_benchmark", "turnover_one_way_monthly"]],
                  pcts=["mean_annual", "vol_annual", "turnover_one_way_monthly"],
                  nums=["ir", "max_drawdown_active", "skew", "excess_kurtosis", "corr_benchmark"]).set_index(["K", "weighting", "period"]))
    figure("fmp", "fig_cum.png")
    say(f"""Lagging the composite trades information for turnover: the information ratio is {num(N['fmp_ir_K1'])} at K = 1 with
{pct(N['fmp_turn_K1'])} monthly turnover, and {num(N['fmp_ir_K12'])} at K = 12 with {pct(N['fmp_turn_K12'])}. In 2017–2024 the
K = 1 information ratio is {num(N['fmp_ir_2017_K1'])}.""")
''')

md(r'''
## 8. Portfolio construction
**Decile long/short.** Each month a cohort goes long the top composite decile and short the bottom decile, equally
weighted, each leg 1/n of capital, and is held n months (n ∈ {1, 3, 6, 12}); collateral earns the risk-free rate, and
shorts pay a borrow fee of 2–25 bps a month by size decile. Every trade is recorded in a ledger that reconciles to the
turnover and the profit and loss. The pre-specified buy-and-hold cohorts are ruined in the 1932–33 rally of
low-quality stocks, when short positions grew to several times capital; cohorts re-weighted to 1/n each month
(the Jegadeesh–Titman form) are therefore the primary convention, **a choice made after the ruin was observed**.
Capacity is the assets under management (2024 dollars) at which the 95th percentile of a position's share of its
stock's monthly dollar volume reaches 10%; there is no price-impact model.

**Linear optimization.** Each quarter a linear program maximizes the composite exposure minus trading costs, long
only with a 2% cap per stock, subject to industry bands of ±δ around the universe's cap-weight industry mix and a
two-way turnover budget τ; costs rise for small and volatile stocks. The grid crosses δ ∈ {2%, 5%, none},
τ ∈ {20%, 40%, 80%, none} and two cost levels, so selecting its best cell is itself a selection exercise; the whole
grid is shown. A variant that scales the alpha into return units (information coefficient × volatility × exposure)
was added after the grid was specified and is shown separately as a sensitivity. Quadratic mean-variance
optimization is excluded: no commercial risk model is available.
''')

code(r'''
if empirical():
    nx = R("longshort", "nxc.csv")
    jt = nx.loc[nx["convention"].eq("monthly re-weighted (JT)") & nx["borrow"].eq("with")].copy()
    jt["ER / IR"] = [f"{pct(e, 2)} / {num(i)}" for e, i in zip(jt.er_over_rf_annual, jt.ir)]
    display(Markdown("**Long/short, monthly re-weighted cohorts (primary, chosen after the buy-and-hold ruin), with borrow: "
                     "annual excess return over rf / information ratio, by n and cost per dollar traded (bps)**"))
    display(jt.pivot(index="n", columns="cost_bps", values="ER / IR"))
    say(f"""With n = 3 at 10 bps the long/short earns {pct(N['ls_er'], 2)} a year over the risk-free rate (IR {num(N['ls_ir'])}), with a
maximum drawdown of {pct(N['ls_mdd'], 2)} in 1932 and a correlation of {num(N['ls_corr'])} with the market; borrow costs
{pct(N['ls_borrow'])} a year. The pre-specified buy-and-hold cohorts are ruined for n ≥ 3 (at {', '.join(N['ls_ruin_dates'])}).""")
    sub = R("longshort", "subperiods_n3_c10.csv")
    sub = sub.loc[sub["borrow"].eq("with")]
    display(Markdown("**n = 3, 10 bps, with borrow, by period (each period starts with fresh capital)**"))
    display(table(sub[["convention", "period", "months", "er_over_rf_annual", "ir", "max_drawdown", "long_contribution_annual",
                       "short_contribution_annual", "stock_hit_rate"]],
                  pcts=["er_over_rf_annual", "max_drawdown", "long_contribution_annual", "short_contribution_annual", "stock_hit_rate"],
                  nums=["ir"]).set_index(["convention", "period"]))
    ia = R("longshort", "industry_attribution.csv")
    display(Markdown("**Industry attribution: regression on the 12 equal-weight industry excess returns (NW 12)**"))
    display(table(ia[["convention", "series", "first", "last", "r2", "residual_alpha_annual", "alpha_t_nw"]],
                  pcts=["residual_alpha_annual"], nums=["r2", "alpha_t_nw"]))
    cap = R("longshort", "capacity.csv")
    cap = cap.loc[cap["convention"].eq("monthly re-weighted (JT)")]
    display(Markdown("**Capacity of the n = 3 long/short (2024 dollars; positions summed by stock and side)**"))
    display(cap.set_index("decade")[["capacity_aum_2024usd_p95_at_10pct", "median_participation_$1B", "p95_participation_$1B"]].assign(
        capacity_aum_2024usd_p95_at_10pct=lambda d: d.iloc[:, 0].map(lambda x: f"${x / 1e9:.2f}B" if x >= 1e9 else f"${x / 1e6:.0f}M"),
        **{"median_participation_$1B": lambda d: d.iloc[:, 1].map(lambda x: pct(x, 2)),
           "p95_participation_$1B": lambda d: d.iloc[:, 2].map(lambda x: pct(x, 1))}))
    figure("longshort", "fig_longshort.png")
''')

code(r'''
if empirical():
    g = R("optimization", "grid.csv")
    spec = g.loc[g["role"].eq("spec")].copy()
    spec["ER / IR / turnover"] = [f"{pct(e, 2)} / {num(i)} / {pct(t)}" for e, i, t in
                                  zip(spec.er_over_bench_annual, spec.ir, spec.turnover_one_way_per_quarter)]
    display(Markdown("**Optimization grid, full sample 1929–2024, net: excess return over CRSP VW / IR / one-way quarterly turnover**"))
    display(spec.pivot(index=["delta", "tau"], columns="c0_bps", values="ER / IR / turnover"))
    gs = R("optimization", "grid_subperiods.csv")
    gs = gs.loc[gs["c0_bps"].eq(30) & gs["period"].isin(["1990–2024", "2017–2024"])].copy()
    gs["Carhart alpha (NW t) [95% CI]"] = [f"{pct(a, 2)} ({num(t)}) {ci(lo, hi)}" for a, t, lo, hi in
                                           zip(gs.carhart_alpha_annual, gs.carhart_alpha_t_nw, gs.carhart_alpha_ci95_low, gs.carhart_alpha_ci95_high)]
    for role, label in [("spec", "Specified grid"), ("sensitivity: Grinold alpha (not in spec)",
                                                     "Sensitivity added after the grid was specified: alpha in return units")]:
        display(Markdown(f"**{label}, c0 = 30 bps: Carhart alpha net of costs**"))
        display(gs.loc[gs["role"].eq(role)].pivot(index=["delta", "tau"], columns="period", values="Carhart alpha (NW t) [95% CI]"))
    figure("optimization", "fig_frontier.png")
    say(f"""Over 1990–2024, net of 30 bps, the specified configurations with 2–5% industry bands and a 20–40% turnover budget have
Carhart alphas of {pct(N['opt_alpha_9024_min'], 2)} to {pct(N['opt_alpha_9024_max'], 2)}, above the paper rule's
{pct(N['ct_alpha|1990–2024|net30'], 2)}; {N['opt_ci_9024_text']}. These are unadjusted, nominal intervals for configurations
selected from a {N['opt_runs_spec']}-run grid, so they overstate the evidence. The gain comes from limiting turnover and from
the industry-neutral composite, not from a new signal. In 2017–2024 the specified configurations' alphas range from
{pct(N['opt_alpha_1724_min'], 2)} to {pct(N['opt_alpha_1724_max'], 2)}, and {N['opt_ci_1724_text']}. These are long-only tilts,
highly correlated with the market.""")
''')

md(r'''
## 9. Declared improvement: a rank buffer
One improvement was declared, with its parameter and success criterion, before any variant result existed. The
binding constraint in the critical tests is cost, so the rule targets turnover: at each rebalance a current holding is
kept if it is still in the low-volatility pool and ranks within the best **150** by combined score; the remaining
slots are filled with the best-ranked other names, equally weighted. No other buffer size was run. The primary metric
is the paired monthly difference (buffer − baseline) in returns net of 30 bps over 1990–2024, with a Newey–West
interval; the rule is called a success if one-way turnover falls by at least 25% **and** the paired difference is
positive, without requiring statistical significance. The 2017–2018 and 2019–2024 rows use data already seen in the
critical tests and are **not a holdout**.
''')

code(r'''
if empirical():
    pr = R("rank_buffer", "paired.csv")
    pr["mean difference (NW SE) [95% CI]"] = [f"{pct(m, 2)} ({pct(s, 2)}) {ci(lo, hi, 2)}" for m, s, lo, hi in
                                              zip(pr.mean_diff_annual, pr.se_nw_annual, pr.ci95_low, pr.ci95_high)]
    pr["Carhart alpha of difference (NW t)"] = [f"{pct(a, 2)} ({num(t)})" for a, t in zip(pr.carhart_alpha_diff_annual, pr.carhart_alpha_diff_t_nw)]
    display(Markdown("**Paired difference, buffer − baseline (annualized)**"))
    display(pr.loc[pr["returns"].isin(["gross", "net30"])].set_index(["period", "returns"])[
        ["months", "mean difference (NW SE) [95% CI]", "Carhart alpha of difference (NW t)"]].unstack("returns"))
    tc = R("rank_buffer", "turnover_concentration.csv")
    display(Markdown("**Turnover, holding period and industry concentration**"))
    display(table(tc[["strategy", "period", "turnover_one_way_per_quarter", "mean_holding_quarters", "hhi_ff12", "max_industry_weight"]],
                  pcts=["turnover_one_way_per_quarter", "max_industry_weight"], nums=["mean_holding_quarters", "hhi_ff12"]).set_index(["period", "strategy"]))
    figure("rank_buffer", "fig_paired_cum.png")
    say(f"""**Verdict under the declared rule: {N['buf_verdict']}.** Over 1990–2024 one-way quarterly turnover falls from
{pct(N['buf_turn_base'])} to {pct(N['buf_turn_buf'])} ({pct(N['buf_turn_red'])} lower), and the paired net-of-30-bps difference is
{pct(N['buf_diff'], 2)} a year {ci(N['buf_lo'], N['buf_hi'], 2)}, so it is not statistically significant; the Carhart alpha of the difference
is {pct(N['buf_alpha'], 2)} (t {num(N['buf_alpha_t'])}). Gross of costs the difference is {pct(N['buf_gross_diff'], 2)}: the buffer
gives up no signal and saves costs. It recovers part of the cost drag but does not change the answer to the critical tests.""")
''')

md(r'''
## 10. Conclusion and limitations
''')

code(r'''
if empirical():
    h = "1990–2024|net30"
    say(f"""**Replication.** On the paper's sample the formula is reproduced closely on return and risk, and the 1963–2016 factor
attribution of the Conservative-minus-Speculative contrast matches the paper almost exactly; turnover is higher than reported
({pct(N['rep_turnover'])} against {pct(N['paper_turnover'], 0)} a quarter), which the paper's unstated definition leaves unexplained.

**Known factors.** The return is largely a bundle of known premia. The long-only portfolio's Carhart alpha over 1929–2016 is
{pct(N['att_cons_carhart_alpha'], 2)}, and over 1963–2016 the five factors plus momentum leave {pct(N['att_cons_ff5umd_alpha'], 2)}.

**Decay and costs.** Carhart alphas are positive and significant before 1990 and not significant afterwards. In the headline period
1990–2024, net of 30 bps, the excess return over the market is {pct(N['ct_excess|' + h], 2)} {ci(N['ct_excess_lo|' + h], N['ct_excess_hi|' + h])}
and the Carhart alpha {pct(N['ct_alpha|' + h], 2)} {ci(N['ct_alpha_lo|' + h], N['ct_alpha_hi|' + h])}; the alpha's break-even cost is
{N['be_alpha|1990–2024']:.0f} bps. **The evidence does not support the claim that the formula beats the market on recent data once known
factors and realistic costs are taken into account.** It remains a cheap, transparent way to hold the low-volatility, momentum and payout
premia with lower volatility than the market, and the contrast between low- and high-risk stocks persists more than the long-only edge
over the market.

**Extensions.** The declared rank buffer cuts turnover and adds {pct(N['buf_diff'], 2)} a year net (not significant); a turnover-budgeted,
industry-banded optimizer does better than the paper rule over 1990–2024 ({pct(N['opt_alpha_9024_min'], 2)}–{pct(N['opt_alpha_9024_max'], 2)}
alpha; {N['opt_ci_9024_text']}, unadjusted for the selection from a {N['opt_runs_spec']}-run grid), and its 2017–2024 alphas lie
between {pct(N['opt_alpha_1724_min'], 2)} and {pct(N['opt_alpha_1724_max'], 2)}. The decile long/short barely
survives costs and borrow fees.""")
''')

md(r'''
**Limitations.**
- *Data release:* WRDS exposes no release identifier; the extract is identified by its time stamp, coverage and file
  hashes, and later CRSP revisions could change individual returns.
- *Dividends:* NPY uses dividends implied by the difference between total and price returns, which includes special
  cash distributions; it agrees with CRSP's ordinary cash distributions in the large majority of stock-months.
- *Share classes and size:* one class per company and security-level market cap may change membership at the margin
  of the 1,000-stock universe relative to the paper's unstated choice.
- *Turnover:* our turnover exceeds the paper's, and the paper does not state its measure.
- *Selection across grids:* the optimization grid and the long/short n × cost table contain many configurations; their
  best cells are selected results. The long/short convention and the optimizer's alpha-scaling sensitivity were chosen
  after results were seen and are labeled so.
- *Post-sample length:* 2017–2024 covers only eight years, and it was seen before the declared improvement was tested.
- *Costs:* proportional costs per dollar traded, with no market-impact model; capacity figures rest on stated volume
  and participation assumptions.
''')

md(r'''
## 11. Reproducibility
```bash
python -m crsp_pipeline extract --user <wrds_username>   # WRDS -> data/raw/ (licensed; not in the repository)
python -m crsp_pipeline build                            # data/raw -> data/ panel, benchmark, factors, audits
python -m research.run_all                               # every study -> results/ (aggregates) + results/manifest.json
python build_notebook.py && python execute_notebook.py   # this notebook, reading results/
python presentation/build_deck.py                        # the slide deck and speaker notes
```
Every table and figure above is read from `results/`, whose files are checked against the sha256 hashes in
`results/manifest.json`; security-level rows never leave the git-ignored `output/` folder. Setting
`CF_RECOMPUTE=1` reruns every study from `data/` before the notebook reads the results.
''')

code(r'''
if empirical():
    man = results.manifest(RESULTS)
    say(f"""Results manifest: {len(man['files'])} files from {len(man['studies'])} studies, last updated {man['updated_utc']} (UTC);
data manifest sha256 `{man['data_manifest_sha256'][:16]}…`; packages {', '.join(f'{k} {v}' for k, v in man['packages'].items())}.""")
    display(pd.DataFrame({s: {"seconds": v["seconds"], "files": v["files"], "run (UTC)": v["run_utc"]}
                          for s, v in man["studies"].items()}).T)
print({"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "mode": MODE})
''')

md(r'''
## Appendix: synthetic demonstration (no data required)
With `CF_MODE=demo` the notebook skips every empirical section and instead runs the same selection and accounting
engine on a seeded synthetic panel. The demonstration only shows that the code runs; its numbers are artificial and
are not evidence about the strategy.
''')

code(r'''
if MODE == "demo":
    from research import engine
    LABEL = "SYNTHETIC DEMO — NOT EMPIRICAL EVIDENCE"
    panel, bench = engine.validate_inputs(*engine.make_demo(seed=9897))
    sig = engine.attach_signals(panel)
    start, end = pd.Timestamp("2003-01-31"), sig["date"].max()
    targets, _ = engine.formation_targets(sig, ["Conservative", "Universe equal weight"], start=start, last=end)
    demo = pd.DataFrame({n: engine.backtest(panel, bench, t, start, end, 10)["net"] for n, t in targets.items()})
    demo["Market"] = bench["market_ret"].reindex(demo.index)
    from research import report
    display(Markdown(f"### {LABEL}"))
    display(report.table({c: demo[c] for c in demo}, bench["rf"]).round(4))
    fig, ax = plt.subplots(figsize=(10, 4.5), layout="constrained")
    for c in demo:
        ax.plot(demo.index, (1 + demo[c]).cumprod(), label=c)
    ax.set(yscale="log", title=f"Growth of $1, net of 10 bps | {LABEL}")
    ax.legend()
    plt.show()
else:
    print("CRSP mode: the synthetic demonstration is not run (set CF_MODE=demo to run it instead of the empirical sections).")
''')

md(r'''
## References
1. Blitz, D., and van Vliet, P. (2018). The Conservative Formula: Quantitative Investing Made Easy. *The Journal of
   Portfolio Management* 44(7), 24–38. Working paper: [SSRN 3145152](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152).
2. Carhart, M. M. (1997). On Persistence in Mutual Fund Performance. *The Journal of Finance* 52(1), 57–82.
3. Fama, E. F., and French, K. R. (2015). A Five-Factor Asset Pricing Model. *Journal of Financial Economics* 116(1), 1–22.
4. Jegadeesh, N., and Titman, S. (1993). Returns to Buying Winners and Selling Losers. *The Journal of Finance* 48(1), 65–91.
5. Newey, W. K., and West, K. D. (1987). A Simple, Positive Semi-Definite, Heteroskedasticity and Autocorrelation
   Consistent Covariance Matrix. *Econometrica* 55(3), 703–708.
6. Shumway, T. (1997). The Delisting Bias in CRSP Data. *The Journal of Finance* 52(1), 327–340.
7. Grinold, R. C., and Kahn, R. N. (2000). *Active Portfolio Management*, 2nd ed. McGraw-Hill.
8. Center for Research in Security Prices (CRSP), US Stock Database (legacy monthly files), via WRDS; Kenneth R. French
   Data Library (factors).
''')

nb = nbf.v4.new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12"},
})
nbf.validate(nb)
if __name__ == "__main__":
    path = ROOT / NOTEBOOK
    nbf.write(nb, path)
    print(f"Created {path}: {len(cells)} cells")
