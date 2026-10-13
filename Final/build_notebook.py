"""Build the Conservative Formula course notebook from saved research results.

Project authors: Yingni Chang and Yikai Shen.

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
# Replicating the Conservative Formula with CRSP Data
**MTH 9897 Systematic Trading · Project 8 · Final report**
**Authors:** Yingni Chang and Yikai Shen

**Reference:** David Blitz and Pim van Vliet (2018), "The Conservative Formula: Quantitative Investing Made Easy",
*The Journal of Portfolio Management* 44(7); [SSRN 3145152](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152).

We implement the paper's US strategy over 1929–2016 and extend the backtest through 2024. We compare our results
with the paper, examine the contribution of dividends and share repurchases, and check how industry weights affect
performance. We also study trading costs and several alternative portfolio constructions. For the recent-period
analysis, we focus on 1990–2024.
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
RESULTS = Path(os.environ.get("CF_RESULTS", str(BASE / "results")))
if MODE == "crsp" and os.environ.get("CF_RECOMPUTE") == "1":   # recompute every study from data/ first
    subprocess.run([sys.executable, "-m", "research.run_all", "--results", str(RESULTS)], cwd=BASE, check=True)
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
Our replication earns {pct(N['rep_cons_compounded'], 2)} compounded annually before costs over 1929–2016, with
{pct(N['rep_cons_volatility'], 2)} volatility. The paper reports {pct(N['paper_cons_compounded'])} and
{pct(N['paper_cons_volatility'])}. Return and risk are close, although our turnover is higher. Using net payout
also produces a different portfolio from using dividends alone, making the adjusted share-count term important.

Recent results are less convincing. Over 1990–2024, at 30 bps per dollar traded, annual excess return over the market
is {pct(N['ct_excess|' + h], 2)} {ci(N['ct_excess_lo|' + h], N['ct_excess_hi|' + h])}, and annual Carhart alpha is
{pct(N['ct_alpha|' + h], 2)} {ci(N['ct_alpha_lo|' + h], N['ct_alpha_hi|' + h])}. Both intervals include zero.
We reproduce much of the paper's historical result, but do not establish reliable recent outperformance after
trading costs and factor adjustment.""")
''')

md(r'''
## 1. What we test
The Conservative Formula is straightforward: start with the 1,000 largest eligible US stocks, keep the half with
the lowest 36-month volatility, and rank them on 12-1 price momentum and net payout yield. The best 100 are equally
weighted and rebalanced quarterly. The paper also forms a Speculative portfolio from high-volatility stocks with
weak momentum and payout scores.

We first compare the published results with our implementation. We then examine factor exposure, changes over time
and trading costs. The comparison periods are 1929–1962, 1963–1989, 1990–2016 and 2017–2024, with 1990–2024 as the
main recent sample. We fixed these periods and the primary tests before computing the post-2016 portfolio returns.
The later construction experiments are discussed separately, including whether their choices were made after
seeing results.

Carhart four-factor alpha is our main factor-adjusted measure; FF5 plus momentum is a robustness check from July
1963. We report returns at 10 and 30 bps per dollar traded and the cost at which excess return or alpha reaches zero.
For compounded and arithmetic returns, volatility and Sharpe ratios, we use 12-month block-bootstrap 95% intervals.
Excess returns and regression alphas use Newey–West intervals with 12 lags. Maximum drawdown is a path statistic,
so we report it without an interval.
''')

md(r'''
## 2. Data
The data are the CRSP monthly stock file (legacy format) for US common stocks (share codes 10 and 11) on NYSE, AMEX
and NASDAQ, with security names, delistings, distributions and the CRSP index file, extracted from WRDS, plus the
Fama–French factors. A pipeline (`crsp_pipeline`) normalizes them to one row per security-month and writes the audit
tables below. Conventions that the paper leaves open are fixed and disclosed:

This run uses the full WRDS web exports downloaded on October 12, 2026, rather than the CRSP trial sample.
`python -m crsp_pipeline.import_web` verifies their hashes, maps the names-file start dates, converts CRSP
missing-return codes to missing values, and removes only identical repeated monthly records from the web join.
The original archives and query receipts are retained in `data/raw/wrds_complete/`.

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
    display(pd.concat([dv[["agree_ordinary_cash", "agree_ordinary_cash_given_distribution"]].map(lambda x: pct(x)),
                       bc[["corr_crsp_vw_vs_ff_market"]].round(4)], axis=1))
    say("The first dividend agreement rate includes zero-dividend months. The conditional rate restricts "
        "the comparison to months with a recorded ordinary cash distribution and is the more demanding check. "
        "Special distributions and ambiguous gaps are separately audited rather than assumed to be ordinary dividends.")
''')

md(r'''
## 3. Portfolio rules and implementation choices
At each quarter-end, we apply the 36-month history requirement before choosing the largest 1,000 stocks. We retain
the low-volatility half, require complete momentum and payout signals, and average their favorable ranks. The best
100 receive equal weights. Weights then drift with returns until the next rebalance. A terminal holding earns its
delisting return and becomes cash, which earns the risk-free rate until reinvestment.

The Speculative portfolio uses the high-volatility half and the weakest combined scores. The single-signal controls
hold the best 100 on each signal; Small holds the 100 smallest universe members. We cannot build the Value control
without book equity, or reproduce Table 2 panels C and D without the q, QMJ and BAB factors.

We charge costs on changes from the drifted weights. The table below records the choices that may differ from the
authors' implementation, particularly share-class selection, the capitalization measure and dividend estimation.
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
    say(f"""Our return and volatility are close to the published values: Conservative compounds at {pct(N['rep_cons_compounded'], 2)} with
{pct(N['rep_cons_volatility'], 2)} volatility (paper {pct(N['paper_cons_compounded'])}, {pct(N['paper_cons_volatility'])}), and the market at
{pct(N['rep_mkt_compounded'], 2)} with {pct(N['rep_mkt_volatility'], 2)} ({pct(N['paper_mkt_compounded'])}, {pct(N['paper_mkt_volatility'])}).
The Speculative portfolio compounds at only {pct(N['rep_spec_compounded'], 2)} with {pct(N['rep_spec_volatility'])} volatility.
Conservative beats the market in {N['decades_cons_beats_mkt']} of {N['decades_n']} decade buckets (partial decades labeled).
The largest gap is Small's simple return ({pct(N['t1_small_simple'])} against {pct(N['paper_small_simple'])}); its compounded return
is within one percentage point. The table below lists the larger gaps. Share-class choices, capitalization and dividend estimation may contribute, but their individual effects are unresolved.""")
    figure("replication", "fig3.png")
    figure("replication", "fig4.png")
    gaps = R("paper_targets", "gaps.csv")
    display(Markdown("**Larger differences: over 1 percentage point for returns/alphas or 5 points for turnover**"))
    display(table(gaps[["table", "item", "paper", "ours", "difference"]], pcts=["paper", "ours", "difference"]))
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
    say(f"""Over 1963–2016 (panel B, N = {N['t2_b_capm_n']}) the CMS alphas are fairly close to the paper: CAPM
{pct(N['t2_b_capm_ours'], 2)} against {pct(N['t2_b_capm_paper'])}, FF3 {pct(N['t2_b_ff3_ours'], 2)} against {pct(N['t2_b_ff3_paper'])},
FF5 {pct(N['t2_b_ff5_ours'], 2)} against {pct(N['t2_b_ff5_paper'])} and FF5 plus momentum {pct(N['t2_b_ff5mom_ours'], 2)} against
{pct(N['t2_b_ff5mom_paper'])}. Over 1929–2016 (panel A) our CAPM and Carhart alphas, {pct(N['t2_a_capm_ours'], 2)} and
{pct(N['t2_a_carhart_ours'], 2)}, are below the paper's {pct(N['t2_a_capm_paper'])} and {pct(N['t2_a_carhart_paper'])}, The differing samples point to the early data as an area to investigate,
but do not establish the cause. For the long-only Conservative portfolio the Carhart alpha is
{pct(N['att_cons_carhart_alpha'], 2)} (NW t {num(N['att_cons_carhart_t'])}), and over 1963–2016 the five factors plus momentum leave
{pct(N['att_cons_ff5umd_alpha'], 2)} (t {num(N['att_cons_ff5umd_t'])}): adding profitability and investment greatly reduces estimated alpha. Net of 30 bps
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
## 6. Factors, costs and changes over time
We use the same Conservative holdings for gross and net returns so that the cost comparison does not mix trading
costs with a different stock-selection rule. The table reports returns, volatility, Sharpe ratios, drawdowns and
factor-adjusted results by period. Carhart uses the market, size, value and momentum factors. FF5 plus momentum
is available only from July 1963.

The rolling plots help show when performance changes, but the windows overlap heavily. We use the fixed-period
estimates for the main comparisons and report their confidence intervals alongside the point estimates.
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
    say(f"""**Results for 1990–2024.** Gross annual compound return is {pct(N['ct_comp|' + g])}
{ci(N['ct_comp_lo|' + g], N['ct_comp_hi|' + g])}, with volatility of {pct(N['ct_vol|' + g])}
{ci(N['ct_vol_lo|' + g], N['ct_vol_hi|' + g])}. The market compounds at {pct(N['ct_mkt_compounded|1990–2024'])} with
{pct(N['ct_mkt_vol|1990–2024'])} volatility. At 30 bps, the strategy's CAGR falls to {pct(N['ct_comp|' + h])}
{ci(N['ct_comp_lo|' + h], N['ct_comp_hi|' + h])}.

Net annual excess return is {pct(N['ct_excess|' + h], 2)} {ci(N['ct_excess_lo|' + h], N['ct_excess_hi|' + h])}.
Carhart alpha is {pct(N['ct_alpha|' + h], 2)} {ci(N['ct_alpha_lo|' + h], N['ct_alpha_hi|' + h])}, while FF5 plus momentum gives
{pct(N['ct_ff5_alpha|' + h], 2)} {ci(N['ct_ff5_alpha_lo|' + h], N['ct_ff5_alpha_hi|' + h], 2)}, which is
{S.significance(N['ct_ff5_alpha_lo|' + h], N['ct_ff5_alpha_hi|' + h])}. The Carhart interval includes zero.
Its break-even cost is {N['be_alpha|1990–2024']:.0f} bps per dollar traded, compared with
{N['be_excess|1990–2024']:.0f} bps for excess return. Lower volatility is the more consistent benefit in this period.

The CMS contrast still has net Carhart alpha of {pct(N['ct_cms_net30_alpha|1990–2024'], 2)}
{ci(N['ct_cms_net30_lo|1990–2024'], N['ct_cms_net30_hi|1990–2024'])}. This is a different question from whether the
long-only portfolio beats the market: the contrast includes shorting the Speculative portfolio.

The fixed-period table and rolling plots show weaker alpha in recent data. For 2017–2024, gross Carhart alpha is
{pct(N['ct_alpha|2017–2024|gross'], 2)} {ci(N['ct_alpha_lo|2017–2024|gross'], N['ct_alpha_hi|2017–2024|gross'])}.
There are only {N['ct_months|2017–2024']} months in that sample, so the wide interval leaves substantial uncertainty.
Flat 10/30-bps costs also do not capture the higher friction that early historical trading may have involved.""")
''')

md(r'''
## 6b. Dividends, repurchases and industry weights
The assignment specifically warns about two sources of noisy results: omitting share repurchases from payout and
ignoring sector positioning. We examine both.

Net payout yield is **dividend yield + 1 − current adjusted shares / trailing 24-month average adjusted shares**.
Repurchases raise the signal and issuance lowers it. We adjust shares for splits so that a split does not look like
a buyback. The share-count term is a net repurchase proxy, rather than a measure of buyback cash spending. To see
what it adds, we compare the formula with a dividends-only version while keeping the universe, low-volatility pool,
signal-completeness rule, momentum, weights, dates and costs the same.

For industry positioning, we compare the portfolio with a cap-weighted reference drawn from the same formation
universe. Each quarter's constituents and industry labels stay fixed while weights drift. Monthly excess return
over CRSP VW is split into industry allocation, selection within industries, and the reference-universe return
minus CRSP VW. Selection includes the allocation/selection interaction. The reported contributions are arithmetic
annual averages, so they should not be read as contributions to CAGR or as causal estimates.

We also test the professor's sector-by-sector approach: allocate 100 slots across FF12 industries in proportion to
universe stock counts, round to whole stocks, and apply the volatility screen and momentum/payout ranking within
each industry. This changes the paper's global screen. We added it after seeing the original results, so it is an
exploratory comparison, without an unseen validation sample.
''')

code(r'''
if empirical():
    pc = R("professor_checks", "payout_comparison.csv")
    view = pc.loc[pc.period.isin(["1929–2016", "1990–2024", "2017–2024"])]
    display(Markdown("**Matched payout comparison and the professor's sector-quota variant**"))
    display(table(view[["period", "strategy", "compounded", "net30_compounded", "volatility", "turnover_quarter"]],
                  pcts=["compounded", "net30_compounded", "volatility", "turnover_quarter"]).set_index(["period", "strategy"]))
    components = R("professor_checks", "payout_components.csv")
    display(Markdown("**Baseline formation holdings: mean payout components and overlap with dividends-only selection**"))
    display(table(components.set_index("period"), pcts=list(components.columns[1:])))
    sa = R("professor_checks", "sector_attribution.csv")
    display(Markdown("**Sector contribution to gross baseline-minus-market arithmetic return**"))
    display(table(sa.set_index("period"), pcts=list(sa.columns[2:])))
    se = R("professor_checks", "sector_exposures.csv")
    display(Markdown("**Mean FF12 weights and maximum monthly portfolio weights, 1929–2016**"))
    display(table(se.loc[se.period.eq("1929–2016")].drop(columns="period").set_index("industry"), pcts=list(se.columns[2:])))
    qc = R("professor_checks", "sector_quota_checks.csv")
    checks = R("professor_checks", "independent_checks.csv")
    display(Markdown("**Independent data, signal, selection, dollar-holdings return and HAC regression checks**"))
    display(checks.set_index("check"))
    base = pc.loc[pc.period.eq("1929–2016") & pc.strategy.eq("Baseline NPY")].iloc[0]
    dividends = pc.loc[pc.period.eq("1929–2016") & pc.strategy.eq("Dividends-only counterfactual")].iloc[0]
    allocation = sa.loc[sa.period.eq("1929–2016")].iloc[0]
    say(f"On the paper's sample, NPY earns {pct(base.compounded, 2)} compounded annually versus "
        f"{pct(dividends.compounded, 2)} for dividends alone. The paired net-30 arithmetic difference is "
        f"{pct(base.paired_npy_minus_div_net30_mean, 2)} {ci(base.paired_ci_low, base.paired_ci_high, 2)}. "
        f"Sector allocation contributes {pct(allocation.allocation_annual, 2)} and stock selection "
        f"{pct(allocation.selection_annual, 2)} annually. All {len(checks)} independent checks pass; "
        f"the quota variant holds 100 names at all {len(qc)} formations, with industry count-weight "
        f"rounding deviations at most {pct(qc.max_abs_industry_weight_minus_universe_count_weight.max(), 2)}.")
''')

md(r'''
## 7. Looking at the signals separately
Here we study each signal rather than the paper's stock-selection screen. Within the monthly universe, we subtract
each FF12 industry's mean exposure, divide by the cross-sectional standard deviation of the demeaned values, and
clip at ±3. The composite is the equal-weight mean of the three neutralized exposures. Forward returns include
delistings and are adjusted by the equal-weight return of the formation industry cohort. Diagnostic cash after
an exit earns zero; cash in the traded baseline earns RF.

IC is the Spearman rank correlation between exposure and future industry-adjusted return. We show its mean,
variance, moving estimates and decay. The mean/sd ratio is distinct from the Newey–West t-statistic, whose lag
choice is h − 1 + 12. Deciles show whether a positive rank correlation also translates into a useful return spread.

For factor-mimicking portfolios, we use monthly WLS with the signal exposures, size, industry dummies and historical
stock-level FF3 betas. These betas were added after the baseline analysis; they use up to 36 completed monthly
returns, with at least 24 factor-covered months (30 at the first formation). The factor portfolio is the sum of
three unit-exposure signal portfolios, a different object from the mean exposure used to rank stocks. Its results
are gross and can involve substantial leverage.
''')

code(r'''
if empirical():
    ic = R("diagnostics", "ic.csv")
    ic["IC: mean (mean/sd; NW t)"] = [f"{num(m, 3)} ({num(r)}; {num(t, 1)})" for m, r, t in zip(ic["mean"], ic.mean_over_sd_literal, ic.t_nw)]
    display(Markdown("**Rank IC by horizon h (months)**"))
    display(ic.pivot(index="exposure", columns="h", values="IC: mean (mean/sd; NW t)"))
    display(Markdown("**Sample variance of monthly IC by horizon**"))
    display(ic.assign(variance=ic["sd"]**2).pivot(index="exposure", columns="h", values="variance"))
    figure("diagnostics", "fig_ic_ma.png")
    ic_monthly = R("diagnostics", "ic_monthly.csv", parse_dates=["date"], index_col="date")
    fig, ax = plt.subplots(figsize=(11, 3.5), layout="constrained")
    for col in [c for c in ic_monthly if c.endswith("|h1")]:
        ax.plot(ic_monthly.index, ic_monthly[col].rolling(12).var(ddof=1), label=col.split("|")[0], lw=.8)
    ax.set(title="12-month moving sample variance of 1-month IC", ylabel="Variance of IC")
    ax.legend(fontsize=8)
    display(fig)
    plt.close(fig)
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
    display(Markdown("**Historical FF3 exposure controls: coverage and look-ahead checks**"))
    risk_controls = R("fmp", "risk_controls.csv")
    display(pd.DataFrame({"formations": [len(risk_controls)], "minimum completed factor months": [risk_controls.factor_months_used.min()],
                          "forward information violations": [risk_controls.forward_information_used.sum()]}))
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
## 8. Long/short portfolios and linear optimization
**Long/short portfolios.** We form a new monthly cohort that buys the top composite decile and sells the bottom
decile. Each leg receives 1/n of capital and is held for n months, with n = 1, 3, 6 or 12. Collateral earns RF and
shorts pay a size-dependent monthly borrow fee of 2–25 bps. Trade ledgers reconcile positions, turnover and P&L.
The original buy-and-hold cohorts lose all capital for n ≥ 3 in the early sample. We then test monthly reweighting
of the surviving cohort names, following the Jegadeesh–Titman form. This alternative was chosen after observing
the losses; we retain both sets of results.

Capacity is the AUM at which the 95th percentile of a position's share of monthly dollar volume reaches 10%.
Historical AUM is scaled to December 2024 market size using CRSP aggregate capitalization. This is not a CPI
adjustment. Monthly volume also cannot tell us the market impact or borrow availability of actual trades.

**Linear optimization.** Quarterly targets maximize composite exposure minus trading costs. We impose long-only
weights, a 2% stock cap, industry bands of ±δ around universe cap weights, and a two-way turnover budget τ.
The grid uses δ = 2%, 5% or none; τ = 20%, 40%, 80% or none; and two cost levels. Costs increase for smaller and
more volatile stocks. We show the full grid because selecting the best cell would overstate the evidence.
A later sensitivity converts exposure into return units using trailing IC and volatility. Since volatility is
annualized, the three-month conversion uses √(3/12). The quadratic model in the next section adds covariance.
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
    display(Markdown("**Capacity of the n = 3 long/short (scaled to 2024 market size; positions summed by stock and side)**"))
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
selected from a {N['opt_runs_spec']}-run grid, so they overstate the evidence. These portfolios use the existing
industry-neutral composite with turnover and industry constraints. In 2017–2024 the specified configurations' alphas range from
{pct(N['opt_alpha_1724_min'], 2)} to {pct(N['opt_alpha_1724_max'], 2)}, and {N['opt_ci_1724_text']}. These are long-only tilts,
highly correlated with the market.""")
''')

md(r'''
## 8b. Adding portfolio risk to the optimizer
This final-review extension maximizes **αᵀw − (γ/2)wᵀΣw − cᵀ|w − w_previous|**. Expected three-month
residual returns use the composite exposure × annual volatility × √(3/12) × trailing mean three-month IC.
Only IC horizons already completed at formation enter that trailing mean; before 12 completed observations,
alpha is zero and the optimizer minimizes risk plus trading costs.

The covariance matrix uses the most recent 36 monthly total returns ending at formation, with 50% shrinkage
toward its diagonal; multiply by three for a three-month covariance under an explicit no-autocorrelation
approximation. This positive semidefinite estimate makes the optimization quadratic through the portfolio variance term. The two fixed risk-aversion values are γ = 5 and 20. We impose a 2% security cap,
FF12 industry bands of ±5 percentage points around the universe's cap weights, and a 40% two-way quarterly
turnover budget after the initial investment. Costs start at 30bps per dollar traded and scale with size and
volatility. If constraints are infeasible, the same disclosed minimum-turnover and industry-bound relaxation
rules as the linear optimizer apply, and their counts are reported.

These are illustrative choices introduced after viewing the baseline, not fitted or validated on an unseen
sample. Shrinkage and risk aversion are not estimated optimal values. Historical risks can change, and using
36 months to estimate a 1,000-stock risk model requires substantial regularization.
''')

code(r'''
if empirical():
    qm = R("mean_variance", "summary.csv")
    qm["Carhart alpha [95% CI]"] = [f"{pct(a, 2)} {ci(lo, hi, 2)}" for a, lo, hi in
                                    zip(qm.carhart_alpha, qm.alpha_ci_low, qm.alpha_ci_high)]
    display(Markdown("**Quadratic portfolios: net returns, risk, costs and market correlation**"))
    display(table(qm[["risk_aversion", "period", "compounded", "volatility", "excess_return_annual", "ir", "hit_ratio",
                      "max_drawdown", "skew_active", "kurtosis_active", "corr_market", "turnover_quarter", "Carhart alpha [95% CI]"]],
                  pcts=["compounded", "volatility", "excess_return_annual", "hit_ratio", "max_drawdown", "turnover_quarter"],
                  nums=["ir", "skew_active", "kurtosis_active", "corr_market"]).set_index(["period", "risk_aversion"]))
    display(Markdown("**Solver feasibility, turnover reconciliation, and absence of risk-window look-ahead**"))
    display(R("mean_variance", "solver_checks.csv").set_index("risk_aversion"))
    capacity = R("mean_variance", "capacity.csv")
    capacity["capacity at 10% volume ($B, 2024 market size)"] = capacity.aum_2024usd_p95_at_10pct/1e9
    display(capacity.loc[capacity.decade.isin(["all", "2020s"])].set_index(["decade", "risk_aversion"])[
        ["positions", "covered", "capacity at 10% volume ($B, 2024 market size)"]])
    say("Both risk-aversion choices are reported. Capacity is a volume-participation proxy without a market-impact "
        "model. These long-only portfolios remain exposed to the market; their correlation is reported, "
        "so they should not be interpreted as market-neutral strategies.")
''')

md(r'''
## 9. Keeping a rank buffer to reduce trading
A holding does not necessarily need to be sold as soon as its rank slips below 100. We test keeping it while it
remains in the low-volatility pool and among the best **150** combined ranks, then filling vacancies with the best
remaining names. We fixed 150 before testing this variant and did not compare other buffer sizes.

We compare monthly buffer-minus-baseline returns over 1990–2024 at 30 bps, using a Newey–West interval. The original
success criterion was at least 25% less one-way turnover and a positive net-return difference; it did not require
statistical significance. We show the confidence interval as well, since passing that criterion alone is weak
evidence of better expected returns. The 2017–2018 and 2019–2024 comparisons use data already seen in the earlier
analysis and are not a holdout.
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
    say(f"""Over 1990–2024, one-way quarterly turnover falls from {pct(N['buf_turn_base'])} to {pct(N['buf_turn_buf'])},
a reduction of {pct(N['buf_turn_red'])}. The net-30-bps paired difference is {pct(N['buf_diff'], 2)} a year
{ci(N['buf_lo'], N['buf_hi'], 2)}. This meets the original mechanical criterion ({N['buf_verdict']}), but the interval
includes zero. The Carhart alpha of the difference is {pct(N['buf_alpha'], 2)} (t {num(N['buf_alpha_t'])}).

The gross difference is {pct(N['buf_gross_diff'], 2)}. Lower turnover helps the cost calculation, but the buffer also
changes holdings, so the net difference cannot be attributed entirely to cost savings. We see it as a useful
trading modification rather than evidence of a stronger underlying signal.""")
''')

md(r'''
## 10. Conclusion and limitations
''')

code(r'''
if empirical():
    h = "1990–2024|net30"
    say(f"""We obtain {pct(N['rep_cons_compounded'], 2)} annual compound return on the paper's sample, close to the published
{pct(N['paper_cons_compounded'])}. Volatility is also close. Turnover is the main unresolved implementation gap:
{pct(N['rep_turnover'])} per quarter versus {pct(N['paper_turnover'], 0)}. The full-sample regression alphas differ too,
although the post-1963 comparisons are closer.

The recent sample is less favorable. At 30 bps over 1990–2024, annual excess return is {pct(N['ct_excess|' + h], 2)}
{ci(N['ct_excess_lo|' + h], N['ct_excess_hi|' + h])}, and annual Carhart alpha is {pct(N['ct_alpha|' + h], 2)}
{ci(N['ct_alpha_lo|' + h], N['ct_alpha_hi|' + h])}. These estimates do not give us strong evidence of recent
outperformance. Lower volatility is a more consistent feature of the portfolio than positive factor-adjusted alpha.

The payout comparison shows why dividends alone are insufficient for this implementation. Industry attribution
helps separate the effect of allocation from stock selection, while the sector quota strategy gives a direct
comparison with the course recommendation. The buffer reduces turnover, but its net gain is not significant.
Some optimizer settings look better in the recent sample; their intervals are unadjusted for testing a
{N['opt_runs_spec']}-run grid, and {N['opt_ci_1724_text']} in 2017–2024. The long/short results are particularly weak
after trading and borrow costs. We would need an unseen sample before treating any of these variants
as evidence of a better strategy.""")
''')

md(r'''
**What we still cannot resolve.**
Our turnover is higher than the paper's. Share-class selection, security-level capitalization and inferred dividends
may affect both rankings and turnover, but we cannot measure their individual effects without the authors' cleaned
data and exact conventions. WRDS did not provide a release identifier; we retain source receipts and file hashes.

Some delisting returns require imputation, and missing held returns use stale-price or price-ratio conventions.
The optimization grid contains many configurations. The monthly-reweighted long/short, return-scaled objective
and quadratic model were considered after results had been seen. Those choices and the short 2017–2024 sample
limit what we can say about future performance. Our cost and capacity estimates also omit market impact and
actual borrow availability.
''')

md(r'''
## 11. Reproducibility
```bash
python -m crsp_pipeline.import_web                       # downloaded web archives -> data/raw/*.parquet
# Alternatively: python -m crsp_pipeline extract --user <wrds_username>
# The private submission package already contains the parquet inputs: skip the import there.
python -m crsp_pipeline build                            # data/raw -> data/ panel, benchmark, factors, audits
python -m research.run_all                               # every study -> results/ (aggregates) + results/manifest.json
python build_notebook.py && python execute_notebook.py   # this notebook, reading results/
python build_report_pdf.py                              # written PDF report
python presentation/build_pdf.py                         # PDF slides and speaker notes
python package_submission.py                             # private ZIP, including licensed data
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
9. Clarabel, [Python quadratic/conic solver interface](https://clarabel.org/stable/python/getting_started_py/), used for the convex quadratic extension.
10. CRSP, [Calculations and Index Methodologies](https://www.crsp.org/wp-content/uploads/guides/CRSP_Calculations_and_Index_Methodologies.pdf),
    corporate-action adjustment conventions.
''')

nb = nbf.v4.new_notebook(cells=cells, metadata={
    "authors": [{"name": "Yingni Chang"}, {"name": "Yikai Shen"}],
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12"},
})
nbf.validate(nb)
if __name__ == "__main__":
    path = ROOT / NOTEBOOK
    nbf.write(nb, path)
    print(f"Created {path}: {len(cells)} cells")
