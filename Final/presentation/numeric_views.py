"""Tables for numerical slide content, built from verified aggregate results.

Project authors: Yingni Chang and Yikai Shen.
These views supply numerical tables for the original content slides.
"""
from research import results, summary as S
from research.summary import pct, num, ci


def make_views(root=results.RESULTS):
    n = S.numbers(root)
    load = lambda study, name: results.load(study, name, root=root)[0]
    ex = load('data_audit', 'extract_summary.json')
    s = ex['sample']
    payout = load('professor_checks', 'payout_comparison.csv')
    sectors = load('professor_checks', 'sector_attribution.csv')
    recent = '1990–2024'
    periods = ('1929–2016', recent)
    run = lambda strategy: [S.one(payout, period=p, strategy=strategy).arithmetic for p in periods]
    gross, net = recent+'|gross', recent+'|net30'
    views = {}

    def add(number, rows, widths, intro=(), notes=(), kind='wide', font=17, prose=False):
        views[number] = dict(rows=rows, widths=widths, intro=list(intro),
                             notes=list(notes), kind=kind, font=font, prose=prose)

    add(3, [
        ['Data item', 'Coverage / count'],
        ['Security-month observations', f"{s['panel_rows']:,}"],
        ['Securities', f"{s['securities']:,}"],
        ['Delistings', f"{s['terminal_rows']:,} total; {s['delist_sources']['imputed_shumway']:,} imputed; "
                       f"{s['delist_sources']['missing_set_zero']:,} set to zero"],
        ['Eligible universe, December 1928', str(s['first_formation_universe_n'])],
        ['First full 1,000-stock universe', s['first_formation_with_full_universe'][:7]],
    ], [.56, .44],
        intro=[f"Monthly CRSP via WRDS: {ex['start'][:7]} to {ex['end'][:7]}; extracted {ex['extracted_at_utc'][:10]}."],
        notes=['One share class per company; dividends implied from total minus price return.',
               'Missing held returns: stale-price carry or in-gap price ratio; every case counted. '
               'WRDS provides no release identifier; time stamp and file hashes identify the extract.'],
        kind='data_cleaning',font=15)
    views[3]['cleaning'] = [
        ('01  Keep delisted stocks', 'Include terminal returns to reduce survivorship bias.'),
        ('02  One common share class', 'Keep one class per company each month to avoid double counting.'),
        ('03  Respect early coverage', f"{s['first_formation_universe_n']} eligible stocks at 1928-12; the universe first reaches 1,000 in {s['first_formation_with_full_universe'][:7]}."),
    ]

    add(5, [
        ['Signal', 'History', 'Calculation'],
        ['Volatility', '36 months', 'Annualized standard deviation of consecutive monthly total returns'],
        ['Momentum', '11 months', 'Compound price returns; exclude the most recent month'],
        ['Dividend yield', '12 months', 'Trailing split-adjusted dividends / current adjusted price'],
        ['Net payout yield', '24-month share average',
         'Dividend yield + 1 − latest adjusted shares / average adjusted shares'],
    ], [.19, .23, .58],
        notes=['A falling share count raises payout yield; new share issuance lowers it.',
               "Quarter-end information determines next month's holdings. No forward return enters selection."],
        prose=True,kind='payout_formula')

    add(6, [
        ['Metric', 'Ours', 'Paper'],
        ['Conservative CAGR', pct(n['rep_cons_compounded'], 2), pct(n['paper_cons_compounded'])],
        ['Conservative volatility', pct(n['rep_cons_volatility'], 2), pct(n['paper_cons_volatility'])],
        ['Market CAGR', pct(n['rep_mkt_compounded'], 2), pct(n['paper_mkt_compounded'])],
        ['Speculative CAGR', pct(n['rep_spec_compounded'], 2), '—'],
        ['Speculative volatility', pct(n['rep_spec_volatility']), '—'],
        ['Quarterly turnover', pct(n['rep_turnover']), pct(n['paper_turnover'], 0)],
        ['Decades beating market', f"{n['decades_cons_beats_mkt']} / {n['decades_n']}", '—'],
    ], [.54, .23, .23], notes=["Gross, 1929–2016. Turnover gap unexplained; paper measure not stated. — = not shown."],
        kind='with_bottom_table', font=14)

    add(7, [
        ['Portfolio', 'Period', 'Model', 'Ours α', 'Paper α', 'Our t'],
        ['CMS', '1963–2016', 'CAPM', pct(n['t2_b_capm_ours'], 2), pct(n['t2_b_capm_paper']), '—'],
        ['CMS', '1963–2016', 'FF5', pct(n['t2_b_ff5_ours'], 2), pct(n['t2_b_ff5_paper']), '—'],
        ['CMS', '1963–2016', 'FF5 + MOM', pct(n['t2_b_ff5mom_ours'], 2), pct(n['t2_b_ff5mom_paper']), '—'],
        ['CMS', '1929–2016', 'CAPM', pct(n['t2_a_capm_ours'], 2), pct(n['t2_a_capm_paper']), '—'],
        ['CMS', '1929–2016', 'Carhart', pct(n['t2_a_carhart_ours'], 2), pct(n['t2_a_carhart_paper']), '—'],
        ['Conservative', '1929–2016', 'Carhart', pct(n['att_cons_carhart_alpha'], 2), '—', num(n['att_cons_carhart_t'])],
        ['Conservative', '1963–2016', 'FF5 + MOM', pct(n['att_cons_ff5umd_alpha'], 2), '—', num(n['att_cons_ff5umd_t'])],
        ['CMS, net 30 bps', '1929–2016', 'Carhart', pct(n['att_cms_carhart_net30_alpha'], 2), '—', num(n['att_cms_carhart_net30_t'])],
    ], [.22, .17, .17, .15, .15, .14],
        intro=['Annual alpha; gross unless labeled net. CMS = Conservative − Speculative; net CMS charges both legs.'],
        notes=['Full-sample gap remains. Adding profitability and investment reduces long-only alpha. '
               '— means the comparison or t-statistic is not shown.'], font=15)

    add(8, [
        ['1929–2016 measure', 'Value'],
        ['Quarterly turnover: ours', pct(n['rep_turnover'])],
        ['Quarterly turnover: paper', pct(n['paper_turnover'], 0)],
        ['Net CAGR at 30 bps', pct(n['rep_cons_net30_compounded'], 2)],
    ], [.68, .32], intro=['Annual cost estimate: quarterly turnover × 8 × cost.'],
        notes=['2017–2024: gross excess return and alpha already ≤ 0, so no break-even.',
               'Early-period break-evens are high, but so were real trading costs then.'],
        kind='with_side_table', font=15)

    grid = load('feedback_costs', 'cost_summary.csv')
    panels=[]
    for period, label in [(recent, 'Broader recent sample'), ('2017–2024', 'Beyond the paper period')]:
        costs=[S.one(grid, period=period, cost_model='flat', reference_bps=c)
               for c in (0, 5, 10, 15, 20, 25, 30)]
        panels.append(dict(title=period, subtitle=f"{label} | Market CAGR {pct(costs[0].market_cagr, 2)}",
            rows=[['Cost (bps)', 'CAGR', 'Above market', 'Carhart alpha']] +
                 [[str(int(r.reference_bps)), pct(r.compounded, 2), pct(r.excess_vs_market, 2),
                   pct(r.carhart_alpha, 2)] for r in costs]))
    add(10, [], [], kind='combined_costs',
        notes=['Same holdings and trades within each period; costs apply to both purchases and sales. '
               'CAGR compounds monthly returns; above-market return is 12 × the mean monthly return difference.',
               'All Carhart alpha 95% intervals include zero. Returns remain positive at every cost tier, '
               'but the 2017–2024 strategy trails the market even before costs.'])
    views[10]['panels']=panels

    row = lambda label, values: [label, *(pct(v, 2) for v in values)]
    npy, div = run('Baseline NPY'), run('Dividends-only counterfactual')
    add(11, [
        ['Annual arithmetic return, gross', *periods],
        row('Net payout rule', npy),
        row('− Dividends only', div),
        row('= Gain from the share-count term', [x-y for x, y in zip(npy, div)]),
    ], [.46, .27, .27],
        intro=['NPY = trailing dividend yield + 1 − latest adjusted shares / 24-month average adjusted shares.',
               'Repurchases raise NPY; issuance lowers it. Splits must leave adjusted shares unchanged.'],
        notes=['Same universe, low-volatility pool, momentum signal, weights and quarterly dates; only the payout '
               'ranking differs. Share changes measure net repurchases after issuance, not buyback cash flow. '
               'Differences use unrounded values.'],
        font=18)

    a = [S.one(sectors, period=p) for p in periods]
    quota = run('Sector quota variant')
    add(12, [
        ['Excess over CRSP market, gross', *periods],
        row('Industry allocation', [x.allocation_annual for x in a]),
        row('+ Stock selection', [x.selection_annual for x in a]),
        row('+ Reference universe − CRSP market', [x.universe_minus_market_annual for x in a]),
        row('= Excess over CRSP market', [x.baseline_minus_market_annual for x in a]),
    ], [.46, .27, .27],
        intro=['Reference: cap-weighted formation universe, quarterly constituents fixed, weights drift.'],
        notes=['Sums and differences use unrounded values. Quota: 100 slots by FF12 security counts, rule applied '
               'within each industry; exploratory, and contributions are not causal.'],
        font=17)
    views[12]['extra'] = dict(
        caption='Industry quota variant against the baseline',
        rows=[['Annual arithmetic return, gross', *periods], row('Industry quota variant', quota),
              row('− Baseline (global screen)', npy), row('= Difference', [x-y for x, y in zip(quota, npy)])],
        widths=[.46, .27, .27])

    add(13, [
        ['Diagnostic', 'Result'],
        ['Composite rank IC, 1 month', f"{num(n['ic_comp_h1'], 3)} (t {num(n['ic_comp_h1_t'], 1)})"],
        ['D10−D1, 1963–1989', pct(n['dec_comp_spread|1963–1989'], 2)],
        ['D10−D1, 1990–2016', pct(n['dec_comp_spread|1990–2016'], 2)],
        ['D10−D1, 2017–2024', pct(n['dec_comp_spread|2017–2024'], 2)],
        ['FMP information ratio, K = 1', num(n['fmp_ir_K1'])],
        ['FMP information ratio, K = 12', num(n['fmp_ir_K12'])],
        ['FMP IR, K = 1, 2017–2024', num(n['fmp_ir_2017_K1'])],
    ], [.66, .34],
        notes=['D10−D1 is a monthly decile spread. FMP portfolios are gross diagnostics and may have leverage.',
               'Low volatility: positive rank IC, flat mean spread (right-skewed high-volatility deciles).'],
        kind='with_picture', font=15)

    add(14, [
        ['Trading / optimization measure', 'Result'],
        ['Long/short annual excess over RF', pct(n['ls_er'], 2)],
        ['Long/short information ratio', num(n['ls_ir'])],
        ['Long/short max drawdown', pct(n['ls_mdd'], 2)],
        ['2020s capacity, scaled to 2024', f"${n['ls_capacity_2020s']/1e9:.1f}B"],
        ['Linear alpha, 1990–2024', f"{pct(n['opt_alpha_9024_min'], 2)} to {pct(n['opt_alpha_9024_max'], 2)}"],
        ['95% intervals excluding zero', f"{n['opt_ci_9024_excl']} / {n['opt_ci_9024_n']}"],
        ['Linear alpha, 2017–2024', f"{pct(n['opt_alpha_1724_min'], 2)} to {pct(n['opt_alpha_1724_max'], 2)}"],
        ['95% intervals excluding zero', f"{n['opt_ci_1724_excl']} / {n['opt_ci_1724_n']}"],
    ], [.63, .37],
        intro=['Long/short: n = 3, 10 bps and borrow. Linear alpha: net 30 bps, annualized.'],
        notes=[f"Monthly reweighting was chosen after buy-and-hold losses ({', '.join(x[:7] for x in n['ls_ruin_dates'])}). "
               'Capacity assumes 10% of volume, scaled to 2024 market size; no impact model. '
               f"Linear recent examples use 2–5% industry bands and 20–40% turnover budgets; intervals are unadjusted, selected from a {n['opt_runs_spec']}-run grid. "
               'Return-scaled alpha is a later sensitivity. We also test a portfolio covariance penalty.'],
        kind='picture_with_notes_below', font=14)

    add(16, [
        ['1990–2024 comparison', 'Result'],
        ['Baseline quarterly turnover', pct(n['buf_turn_base'])],
        ['Buffer quarterly turnover', pct(n['buf_turn_buf'])],
        ['Relative turnover reduction', pct(n['buf_turn_red'])],
        ['Paired net-30 gain, per year', f"{pct(n['buf_diff'], 2)}\n{ci(n['buf_lo'], n['buf_hi'], 2)}"],
        ['Paired gross gain, per year', pct(n['buf_gross_diff'], 2)],
    ], [.64, .36],
        intro=['Keep holdings while eligible and within the best 150 ranks.'],
        notes=['Net paired interval includes zero: not significant. The buffer changes holdings as well as costs.',
               'The recent period was already seen when we tested this variant.'], kind='with_picture', font=15)
    return views
