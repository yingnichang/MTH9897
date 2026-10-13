"""Build the slide deck and speaker notes from the tracked results (results/, through the hash-checked loader).

    python presentation/build_deck.py            # -> presentation/conservative_formula.pptx, presentation/speaker_notes.md

Every number on a slide is formatted from `research.summary.numbers()` or read from a results table; figures are the
PNGs in results/. Run `python presentation/build_pdf.py` for the requested PDF deliverable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

FINAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FINAL))
from research import results  # noqa: E402
from research import summary as S  # noqa: E402
from research.summary import ci, num, pct  # noqa: E402

INK, ACCENT, MUTED = RGBColor(0x1F, 0x2A, 0x33), RGBColor(0x17, 0x6B, 0x87), RGBColor(0x6B, 0x75, 0x7D)


class Deck:
    def __init__(self, root: Path):
        self.root = root
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(13.333), Inches(7.5)
        self.notes: list[tuple[str, str]] = []

    def slide(self, title: str, bullets=(), notes: str = "", image=None, table: pd.DataFrame | None = None,
              subtitle: str | None = None, text_width: float = 6.2, image_width: float | None = None):
        """Title, then bullets on the left and a figure or table on the right. With both a figure and a table, the
        table spans the full width below the figure. Long bullet lists use a smaller font."""
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        tb = s.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.3), Inches(0.9)).text_frame
        tb.word_wrap = True
        p = tb.paragraphs[0]
        p.text, p.font.size, p.font.bold, p.font.color.rgb = title, Pt(28), True, INK
        if subtitle:
            q = tb.add_paragraph()
            q.text, q.font.size, q.font.color.rgb = subtitle, Pt(15), MUTED
        right = image is not None or table is not None
        width = text_width if right else 12.3
        if bullets:
            body = s.shapes.add_textbox(Inches(0.5), Inches(1.4), Inches(width), Inches(5.7)).text_frame
            body.word_wrap = True
            big = 15 if sum(len(b) for b in bullets) / width < 75 else 13
            for i, b in enumerate(bullets):
                para = body.paragraphs[0] if i == 0 else body.add_paragraph()
                level = 1 if b.startswith("  ") else 0
                para.text, para.level = b.strip(), level
                para.font.size, para.font.color.rgb = Pt(big if level == 0 else big - 2), INK if level == 0 else MUTED
                para.space_after = Pt(6)
        left = Inches(0.5 + width + 0.2) if bullets else Inches(0.5)
        avail = Inches(12.3 - (width + 0.2 if bullets else 0))
        top = Inches(1.4)
        if image is not None:
            p = image if isinstance(image, Path) else results.path(*image, root=self.root)
            w = Inches(image_width) if image_width else avail
            pic = s.shapes.add_picture(str(p), left, Inches(1.4), width=w)
            if table is not None:                    # the table goes below the figure, across the slide
                top, left, avail = pic.top + pic.height + Inches(0.15), Inches(0.5), Inches(12.3)
        if table is not None:
            rows, cols = table.shape[0] + 1, table.shape[1] + 1
            t = s.shapes.add_table(rows, cols, left, top, avail, Inches(0.3 * rows)).table
            cells = [[table.index.name or ""] + [str(c) for c in table.columns]] + \
                    [[str(i)] + [str(v) for v in r] for i, r in zip(table.index, table.to_numpy())]
            for r, vals in enumerate(cells):
                for c, v in enumerate(vals):
                    cell = t.cell(r, c)
                    cell.text = v
                    for para in cell.text_frame.paragraphs:
                        para.font.size = Pt(11)
                        para.font.bold = r == 0
        s.notes_slide.notes_text_frame.text = notes
        self.notes.append((title, notes))
        return s

    def table_headers(self) -> list[str]:
        """Header cells (first row and first column) of every table on every slide."""
        out = []
        for sl in self.prs.slides:
            for sh in sl.shapes:
                if sh.has_table:
                    rows = list(sh.table.rows)
                    out += [c.text for c in rows[0].cells] + [r.cells[0].text for r in rows]
        return out


def build(root: Path = results.RESULTS, out_dir: Path = FINAL / "presentation") -> Path:
    N = S.numbers(root)
    L = lambda s, n, **k: results.load(s, n, root=root, **k)[0]
    d = Deck(root)
    h, g = "1990–2024|net30", "1990–2024|gross"

    d.slide("The Conservative Formula",
            subtitle="Yingni Chang · MTH 9897 Project 8 · CRSP replication, 1929–2024",
            bullets=["Paper: Blitz and van Vliet (2018), The Conservative Formula, Journal of Portfolio Management 44(7)",
                     "Replicate the US results on the paper's sample, 1929–2016",
                     "Then test three questions fixed in advance: known factors, decay, costs",
                     "Headline period: 1990–2024 (2017–2024 is post-sample)"],
            notes="The replication is the benchmark, not the conclusion. The three questions and their periods were fixed "
                  f"before any 2017–2024 return was computed; the first load of those data is time-stamped {N['freeze_utc']}.")

    d.slide("The question",
            bullets=["The rule: 1,000 largest US stocks → low-volatility half → rank on 12-1 momentum and net payout yield → best 100, equal weight, quarterly",
                     "1. Known factors: is the return explained by Carhart (primary) or FF5 + momentum (robustness)?",
                     "2. Decay: fixed periods 1929–1962, 1963–1989, 1990–2016, 2017–2024, plus rolling 120-month windows",
                     "3. Costs: net of 10 and 30 bps per dollar traded; break-even cost of the excess return and the alpha",
                     "All estimates with Newey–West (12 lags) or block-bootstrap intervals"],
            notes="CAPM alphas are shown only for comparison with the paper. A positive average return is not treated as "
                  "evidence unless its interval excludes zero.")

    ex = L("data_audit", "extract_summary.json")
    s = ex["sample"]
    d.slide("Data and audits",
            bullets=[f"CRSP monthly stock file via WRDS, extracted {ex['extracted_at_utc'][:10]}; months {ex['start'][:7]} to {ex['end'][:7]}",
                     f"{s['panel_rows']:,} security-months, {s['securities']:,} securities, {s['terminal_rows']:,} delistings "
                     f"({s['delist_sources']['imputed_shumway']} imputed, {s['delist_sources']['missing_set_zero']} set to zero)",
                     f"Universe: {s['first_formation_universe_n']} stocks in December 1928; the full 1,000 from {s['first_formation_with_full_universe'][:7]}",
                     "One share class per company; dividends implied from total minus price return",
                     "Held stocks without a monthly return: stale-price carry or in-gap price ratio, every case counted",
                     "No release identifier on WRDS: the extract is identified by time stamp and file hashes"],
            notes="All audit tables (coverage, exclusions, missing returns, delistings, dividends, benchmark) are in the "
                  "notebook's data section; no security-level row appears in the report.")

    dev = L("replication", "deviations.csv").set_index("item")["ours"]
    d.slide("Baseline rule and deviations from the paper",
            bullets=["Paper order: history screen → top 1,000 by market cap → low-volatility half → ranks among complete signals",
                     "Weights drift between rebalances; delisted holdings become cash; costs charged per dollar traded",
                     "Controls: Speculative (high-volatility half, weakest scores), standalone signals, Small, CRSP VW market",
                     "Excluded: Value (no book equity in CRSP) and Table 2 panels C–D (factors not in our sources)"],
            table=dev.to_frame("our convention").head(6).rename_axis("deviation"), text_width=5.6,
            notes="Every deviation is disclosed with its direction or magnitude in the notebook's deviations table.")

    t1 = L("paper_targets", "table1_vs_paper.csv")
    d.slide("Signal construction and timing",
            bullets=["Volatility: annualized standard deviation of 36 consecutive monthly total returns",
                     "Momentum: compound 11 monthly price returns, excluding the most recent month",
                     "Dividend yield: trailing 12 months of split-adjusted dividends divided by the current adjusted price",
                     "Net payout yield: dividend yield + 1 − latest adjusted shares / average adjusted shares over 24 months",
                     "A falling share count raises payout yield; new share issuance lowers it",
                     "Quarter-end information determines next month's holdings. No forward return enters selection."],
            notes="The 12-month dividend window is a disclosed convention: the paper specifies the share-count ratio "
                  "but does not fully specify the dividend window. Price returns exclude distributions; total returns "
                  "include them. Adjusting both prices and shares prevents a stock split from looking like a buyback.")

    t1 = t1.loc[t1["row"].isin(["Return (compounded)", "Volatility"]) & t1["status"].eq("compared")]
    t1["paper / ours"] = t1["paper"].map(pct) + " / " + t1["ours"].map(pct)
    tab = t1.pivot(index="row", columns="column", values="paper / ours")[["Formula", "Market", "Small", "Momentum", "Lowvol", "NPY"]]
    d.slide("Replication 1929–2016: close on return and risk",
            bullets=[f"Conservative {pct(N['rep_cons_compounded'], 2)} compounded, {pct(N['rep_cons_volatility'], 2)} volatility "
                     f"(paper {pct(N['paper_cons_compounded'])}, {pct(N['paper_cons_volatility'])})",
                     f"Market {pct(N['rep_mkt_compounded'], 2)} (paper {pct(N['paper_mkt_compounded'])})",
                     f"Speculative {pct(N['rep_spec_compounded'], 2)} with {pct(N['rep_spec_volatility'])} volatility",
                     f"Conservative beats the market in {N['decades_cons_beats_mkt']} of {N['decades_n']} decades",
                     f"Turnover {pct(N['rep_turnover'])} a quarter vs the paper's {pct(N['paper_turnover'], 0)} (unexplained; measure not stated)"],
            image=("replication", "fig3.png"), table=tab.rename_axis("paper / ours"), text_width=5.0, image_width=6.5,
            notes="Gross of costs, paper definitions. Candidate explanations and unresolved material gaps are "
                  "listed in the notebook; no parameter was adjusted to force agreement with the paper.")

    d.slide("Factor attribution (Table 2): largely known premia",
            bullets=[f"CMS (Conservative − Speculative), 1963–2016: CAPM {pct(N['t2_b_capm_ours'], 2)} vs {pct(N['t2_b_capm_paper'])}; "
                     f"FF5 {pct(N['t2_b_ff5_ours'], 2)} vs {pct(N['t2_b_ff5_paper'])}; FF5 + MOM {pct(N['t2_b_ff5mom_ours'], 2)} vs {pct(N['t2_b_ff5mom_paper'])}",
                     f"1929–2016: CAPM {pct(N['t2_a_capm_ours'], 2)} vs {pct(N['t2_a_capm_paper'])}; Carhart {pct(N['t2_a_carhart_ours'], 2)} vs {pct(N['t2_a_carhart_paper'])} "
                     "(gap is pre-1963)",
                     f"Conservative long-only: Carhart alpha {pct(N['att_cons_carhart_alpha'], 2)} (t {num(N['att_cons_carhart_t'])})",
                     f"  FF5 + momentum, 1963–2016: {pct(N['att_cons_ff5umd_alpha'], 2)} (t {num(N['att_cons_ff5umd_t'])}) — profitability and investment explain it",
                     f"CMS net of 30 bps, both legs paying: Carhart {pct(N['att_cms_carhart_net30_alpha'], 2)} (t {num(N['att_cms_carhart_net30_t'])})"],
            notes="Paper t-values are compared with our OLS t; Newey–West t-statistics are reported alongside in the notebook.")

    be = L("critical_tests", "breakeven.csv")
    be["bps"] = [f"{b:.0f}" if st == "found" else "none" for b, st in zip(be.breakeven_bps, be.status)]
    bet = be.pivot(index="period", columns="measure", values="bps").rename(columns={
        "net Carhart alpha": "alpha", "net arithmetic excess over the market": "excess return"}).rename_axis("break-even, bps")
    d.slide("Costs (Table 4) and break-even",
            bullets=[f"Paper cost arithmetic reproduced: turnover × 8 × cost; our turnover {pct(N['rep_turnover'])} vs {pct(N['paper_turnover'], 0)}",
                     f"Net of 30 bps, 1929–2016: {pct(N['rep_cons_net30_compounded'], 2)} compounded",
                     f"1990–2024 break-even: {N['be_excess|1990–2024']:.0f} bps (excess return), {N['be_alpha|1990–2024']:.0f} bps (alpha)",
                     ("2017–2024: gross excess return and alpha already ≤ 0, so no break-even"
                      if N["be_alpha_status|2017–2024"] == "<= 0" and N["be_excess_status|2017–2024"] == "<= 0"
                      else f"2017–2024 break-even: {N['be_alpha|2017–2024']:.0f} bps (alpha)"),
                     "Early-period break-evens are high, but so were real trading costs then"],
            table=bet, text_width=6.6,
            notes="Break-even is the cost per dollar traded at which the net excess return or net Carhart alpha reaches zero.")

    rows = []
    for per in S.PERIODS:
        rows.append({"period": per, "months": N[f"ct_months|{per}"],
                     "excess, gross": pct(N[f"ct_excess|{per}|gross"]),
                     "Carhart α gross (t)": f"{pct(N[f'ct_alpha|{per}|gross'])} ({num(N[f'ct_alpha_t|{per}|gross'])})",
                     "Carhart α net 30 (t)": f"{pct(N[f'ct_alpha|{per}|net30'])} ({num(N[f'ct_alpha_t|{per}|net30'])})"})
    d.slide("Decay: alphas fade after 1990",
            bullets=[f"Carhart alpha (gross): {pct(N['ct_alpha|1929–1962|gross'])} → {pct(N['ct_alpha|1963–1989|gross'])} → "
                     f"{pct(N['ct_alpha|1990–2016|gross'])} → {pct(N['ct_alpha|2017–2024|gross'])}",
                     "Significant before 1990, not after",
                     f"2017–2024 is only {N['ct_months|2017–2024']} months: interval {ci(N['ct_alpha_lo|2017–2024|gross'], N['ct_alpha_hi|2017–2024|gross'])}"],
            image=("critical_tests", "fig_rolling.png"), table=pd.DataFrame(rows).set_index("period"), text_width=7.0,
            image_width=5.0,
            notes="No evidence of outperformance in 2017–2024, rather than proof of failure: the interval is wide.")

    d.slide("Headline 1990–2024: no significant net alpha",
            bullets=[f"Gross: excess over market {pct(N['ct_excess|' + g], 2)} {ci(N['ct_excess_lo|' + g], N['ct_excess_hi|' + g])}; "
                     f"Carhart alpha {pct(N['ct_alpha|' + g], 2)} (t {num(N['ct_alpha_t|' + g])})",
                     f"Net of 30 bps: excess {pct(N['ct_excess|' + h], 2)} {ci(N['ct_excess_lo|' + h], N['ct_excess_hi|' + h])}; "
                     f"alpha {pct(N['ct_alpha|' + h], 2)} {ci(N['ct_alpha_lo|' + h], N['ct_alpha_hi|' + h])}",
                     f"FF5 + momentum alpha, net of 30 bps: {pct(N['ct_ff5_alpha|' + h], 2)} (t {num(N['ct_ff5_t|' + h])})",
                     f"Still lower risk: {pct(N['ct_cons_compounded|1990–2024'])} compounded with {pct(N['ct_cons_vol|1990–2024'])} volatility "
                     f"(market {pct(N['ct_mkt_compounded|1990–2024'])}, {pct(N['ct_mkt_vol|1990–2024'])})",
                     f"Cost-inclusive CMS alpha {pct(N['ct_cms_net30_alpha|1990–2024'], 2)} (t {num(N['ct_cms_net30_t|1990–2024'])})"],
            notes="The evidence does not support the claim that the formula beats the market on recent data once known factors "
                  "and realistic costs are taken into account.")

    pc = L("professor_checks", "payout_comparison.csv")
    payout = pc.loc[pc.period.eq("1929–2016")].set_index("strategy")
    base, div = payout.loc["Baseline NPY"], payout.loc["Dividends-only counterfactual"]
    d.slide("Net payout: dividends and share repurchases",
            bullets=["NPY = trailing dividend yield + 1 − latest adjusted shares / 24-month average adjusted shares",
                     "Repurchases raise NPY; share issuance lowers it. Splits must leave the adjusted share count unchanged",
                     f"1929–2016 gross CAGR: {pct(base.compounded, 2)} using NPY versus {pct(div.compounded, 2)} using dividends alone",
                     f"Paired net-30 arithmetic gain from NPY: {pct(base.paired_npy_minus_div_net30_mean, 2)} per year "
                     f"{ci(base.paired_ci_low, base.paired_ci_high, 2)}",
                     "Same universe, low-volatility pool, momentum signal, weights, quarterly dates, and costs in the comparison",
                     "Share-count change measures net repurchases after issuance; it is not reported buyback cash flow"],
            notes="This directly addresses the professor's payout warning. The latest/24-month-average share ratio "
                  "comes from paper page 4; the 12-month dividend window is a disclosed convention. The review adds "
                  "synthetic tests for repurchases, issuance and split neutrality, plus 1,200 independent signal calculations.")

    attr = L("professor_checks", "sector_attribution.csv").set_index("period")
    a = attr.loc["1929–2016"]
    quota = payout.loc["Sector quota variant"]
    d.slide("Sector positioning: allocation versus selection",
            bullets=["Paper scores are compared across sectors (page 4); the professor's sector-aware variant is reported separately",
                     f"1929–2016 gross arithmetic excess return: {pct(a.baseline_minus_market_annual, 2)} per year",
                     f"  Industry allocation {pct(a.allocation_annual, 2)} + stock selection {pct(a.selection_annual, 2)} "
                     f"+ reference-to-CRSP-market difference {pct(a.universe_minus_market_annual, 2)}",
                     "Reference: cap-weighted formation universe, quarterly constituents and industries fixed, weights drift, delistings to cash",
                     f"Sector variant: 100 slots proportional to industry security counts; apply the rule separately within each FF12 industry. "
                     f"Gross CAGR {pct(quota.compounded, 2)}, net-30 {pct(quota.net30_compounded, 2)}",
                     "The sector variant is exploratory and changes the paper's global low-volatility screen. Contributions are arithmetic, not causal"],
            notes="Exact monthly allocation plus selection plus the universe-to-market bridge reconciles to baseline excess "
                  "returns. Selection includes interaction. The quota rule follows the professor's Enhanced Momentum "
                  "example, using counts rather than cap weights, largest-remainder rounding and equal stock weights.")

    d.slide("Signal diagnostics",
            bullets=[f"Composite rank IC (1 month): {num(N['ic_comp_h1'], 3)} (NW t {num(N['ic_comp_h1_t'], 1)})",
                     f"Decile spread D10−D1: {pct(N['dec_comp_spread|1963–1989'], 2)} (1963–1989), {pct(N['dec_comp_spread|1990–2016'], 2)} (1990–2016), "
                     f"{pct(N['dec_comp_spread|2017–2024'], 2)} (2017–2024)",
                     f"Factor-mimicking paper portfolio: IR {num(N['fmp_ir_K1'])} at K = 1, {num(N['fmp_ir_K12'])} at K = 12",
                     f"  2017–2024 IR at K = 1: {num(N['fmp_ir_2017_K1'])}",
                     "Low volatility: positive rank IC, flat mean spread (right-skewed high-volatility deciles)"],
            image=("diagnostics", "fig_decay.png"), text_width=5.6,
            notes="Signals are industry-neutralized, standardized and clipped at ±3; returns are industry-adjusted.")

    # A single-panel chart keeps the slide's labels legible. Its values come from the verified grid.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    grid = L("optimization", "grid.csv")
    fig, ax = plt.subplots(figsize=(7, 4.8), layout="constrained")
    for delta, color in [("2%", "#176B87"), ("5%", "#C0504D"), ("none", "#7F7F7F")]:
        for c0, marker in [(10, "o"), (30, "s")]:
            curve = grid.loc[grid.role.eq("spec") & grid.delta.eq(delta) & grid.c0_bps.eq(c0)].sort_values("turnover_one_way_per_quarter")
            ax.plot(100*curve.turnover_one_way_per_quarter, curve.ir, marker=marker, color=color, label=f"Band {delta}; {c0}bps")
    ax.set(xlabel="One-way quarterly turnover (%)", ylabel="Net information ratio", title="Linear optimizer: 1929–2024")
    ax.tick_params(labelsize=11)
    ax.legend(fontsize=10, ncol=2)
    chart = out_dir / "build" / "linear_spec.png"
    chart.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(chart, dpi=180)
    plt.close(fig)

    d.slide("Construction: long/short and optimization",
            bullets=[f"Decile long/short, n = 3, 10 bps, borrow: {pct(N['ls_er'], 2)} a year, IR {num(N['ls_ir'])}, max drawdown {pct(N['ls_mdd'])}",
                     "  Monthly re-weighted cohorts: chosen after the pre-specified buy-and-hold cohorts were ruined "
                     f"({', '.join(x[:7] for x in N['ls_ruin_dates'])})",
                     f"  Capacity 2020s ≈ ${N['ls_capacity_2020s'] / 1e9:.1f}B (scaled to 2024 market size; 10% of volume; no impact model)",
                     f"Linear optimizer, 1990–2024 net 30: Carhart alpha {pct(N['opt_alpha_9024_min'], 2)}–{pct(N['opt_alpha_9024_max'], 2)} "
                     f"(2–5% bands, 20–40% turnover budget); {N['opt_ci_9024_text']}",
                     f"  Unadjusted intervals, selected from a {N['opt_runs_spec']}-run grid; 2017–2024 alphas "
                     f"{pct(N['opt_alpha_1724_min'], 2)} to {pct(N['opt_alpha_1724_max'], 2)} ({N['opt_ci_1724_text']}); "
                     "return-scaled alpha is a post-spec sensitivity",
                     "The next slide adds the assignment's quadratic mean-variance extension"],
            image=chart, text_width=6.0,
            notes="Labels matter: the long/short convention and the optimizer's alpha-scaling sensitivity were chosen after "
                  "results were seen.")

    qm = L("mean_variance", "summary.csv")
    qr = qm.loc[qm.period.eq("1990–2024")].set_index("risk_aversion")
    qcheck = L("mean_variance", "solver_checks.csv")
    qt = pd.DataFrame({"Net CAGR": qr.compounded.map(lambda x: pct(x, 2)),
                       "Volatility": qr.volatility.map(lambda x: pct(x, 2)),
                       "IR": qr.ir.map(num), "Market corr.": qr.corr_market.map(num)})
    qt.index = [f"γ = {g:g}" for g in qt.index]
    qt.index.name = "1990–2024"
    d.slide("Quadratic mean-variance optimization",
            bullets=["Maximize expected return − half risk aversion × portfolio variance − trading costs",
                     "Covariance: trailing 36 monthly returns, 50% diagonal shrinkage; the window ends at formation",
                     "Return alpha: completed trailing IC × annual volatility × √(3/12) × composite exposure",
                     "Quarterly: 2% stock cap, industry bands ±5pp, turnover budget 40%; scaled costs start at 30bps",
                     f"Two fixed risk aversions (5 and 20); max constraint violation {qcheck.max_constraint_violation.max():.1e}; "
                     f"turnover relaxations {int(qcheck.turnover_relaxations.sum())}",
                     "Added during final review after observing the baseline; no unseen test or claim of optimal parameters"],
            table=qt, text_width=6.6,
            notes="This fulfills the quadratic optimization requirement using an estimated risk model. A positive "
                  "semidefinite 50% diagonal shrinkage estimate regularizes 1,000 stocks with 36 observations. Covariance "
                  "is scaled to three months assuming no autocorrelation. Both gamma values and all feasibility "
                  "relaxations are reported in the notebook. These are long-only portfolios with substantial market exposure.")

    d.slide("Declared improvement: rank buffer of 150",
            bullets=["Declared before any result: keep holdings ranked within the best 150; success = turnover −25% and positive net difference",
                     f"Verdict: {N['buf_verdict']}",
                     f"Turnover {pct(N['buf_turn_base'])} → {pct(N['buf_turn_buf'])} a quarter ({pct(N['buf_turn_red'])} lower)",
                     f"Net-of-30 paired difference {pct(N['buf_diff'], 2)} a year {ci(N['buf_lo'], N['buf_hi'], 2)}: not significant",
                     f"Gross paired difference {pct(N['buf_gross_diff'], 2)}; the observed difference does not prove unchanged signal quality",
                     "2017–2024 was already seen: not a holdout"],
            image=("rank_buffer", "fig_paired_cum.png"), text_width=5.6,
            notes="The buffer recovers part of the cost drag but does not change the answer to the critical tests.")

    d.slide("Conclusion and limitations",
            bullets=["Replication close on return and risk; Table 2 panel B reproduced almost exactly",
                     "The return is largely a bundle of low-volatility, momentum, profitability and investment premia",
                     f"Alphas decay; 1990–2024 net of 30 bps: alpha {pct(N['ct_alpha|' + h], 2)} {ci(N['ct_alpha_lo|' + h], N['ct_alpha_hi|' + h])}",
                     "No evidence that the formula beats the market on recent data after known factors and costs",
                     "A cheap, transparent way to hold these premia with lower volatility than the market",
                     "Limitations: no CRSP release identifier; implied dividends; share-class and size conventions; "
                     "turnover above the paper's; selection across grids; a short post-sample"],
            notes="These statements follow the accepted conclusions of the replication, attribution and critical tests.")

    man = results.manifest(root)
    d.slide("Reproducibility",
            bullets=["python -m crsp_pipeline.import_web   (full web exports; licensed data kept private)",
                     "python -m crsp_pipeline build",
                     "python -m research.run_all   → results/ (aggregates) + results/manifest.json",
                     "python build_notebook.py && python execute_notebook.py",
                     "python presentation/build_pdf.py   (PDF slides and speaker notes)",
                     f"{len(man['files'])} result files with sha256 hashes; data manifest {man['data_manifest_sha256'][:12]}…"],
            notes="Every slide number is read from results/ through the loader, which refuses a file whose hash differs "
                  "from the manifest. Security-level rows stay in the git-ignored output/ folder.")

    bad = results.security_headers(d.table_headers())
    if bad:
        raise ValueError(f"security-level identifier column on a slide: {bad}")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "conservative_formula.pptx"
    d.prs.save(path)
    lines = ["# Speaker notes", "", "Generated by `presentation/build_deck.py` from `results/`.", ""]
    for i, (title, note) in enumerate(d.notes, 1):
        lines += [f"## {i}. {title}", "", note, ""]
    (out_dir / "speaker_notes.md").write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    p = build()
    print(f"Wrote {p} and {p.parent / 'speaker_notes.md'}")
