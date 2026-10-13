"""Factor-mimicking portfolios and the lagged paper portfolio (7D-F), formations 1928-12 .. 2024-11. Ported unchanged
from the closed task 2026-10-11-factor-mimicking. Reads the diagnostics universe cache (rebuilt when missing).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from crsp_pipeline import config
from research import diagnostics as dg, fmp, stats

NAME = 'fmp'
DEPENDS = ('diagnostics',)
FIXED_END = "2024-12-31"                       # sample fixed at 2024-12: run_all rejects another --end
FILES = {
    'factor_returns.csv': {'description': 'Monthly unit-exposure FMP returns (WLS with industries and size), leverage and the composite exposure check', 'window': '1929-01 .. 2024-12', 'returns': 'gross', 'role': 'primary'},
    'paper_portfolio.csv': {'description': 'Lagged composite paper portfolio (K = 1, 3, 6, 12; equal and exponential): active return, turnover, leverage', 'window': '1929-01 .. 2024-12', 'returns': 'gross', 'role': 'primary'},
    'paper_metrics.csv': {'description': 'Paper portfolio metrics (IR, turnover, drawdown, skew, kurtosis, benchmark correlation) by K, weighting and period', 'window': '1929-01 .. 2024-12', 'returns': 'gross', 'role': 'primary'},
    'carhart_crosscheck.csv': {'description': 'Cross-check (not part of 7D-F): K = 1 composite on Carhart factors', 'window': '1929-01 .. 2024-12', 'returns': 'gross', 'role': 'exploratory'},
    'fmp_leverage.csv': {'description': 'FMP gross leverage and breadth by decade', 'window': '1929-01 .. 2024-12', 'returns': 'n/a', 'role': 'check'},
    'size_clip_counts.csv': {'description': 'Size exposure clip counts', 'window': '1929-01 .. 2024-12', 'returns': 'n/a', 'role': 'check'},
    'fig_cum.png': {'description': 'Cumulative active return of the paper portfolio and cumulative factor returns', 'window': '1929-01 .. 2024-12', 'returns': 'gross', 'role': 'primary'},
}
KS, SCHEMES = [1, 3, 6, 12], ["equal", "exponential"]
PERIODS = {"1929–2024": ("1929-01-31", "2024-12-31"), "1929–1962": ("1929-01-31", "1962-12-31"),
           "1963–1989": ("1963-01-31", "1989-12-31"), "1990–2016": ("1990-01-31", "2016-12-31"),
           "2017–2024": ("2017-01-31", "2024-12-31")}

def run(ctx):
    out_dir, log = ctx.out(NAME), ctx.log
    assert pd.Timestamp(ctx.end) == pd.Timestamp("2024-12-31"), "this study's sample is fixed at 2024-12"
    e = pd.read_parquet(ctx.universe_cache())
    e["size_z"], size_counts = dg.neutralize(np.log(e["mktcap"]), e["date"], e["group"])
    bench = pd.read_csv(config.BENCHMARK_FILE, parse_dates=["date"], index_col="date")["market_ret"]
    fac = pd.read_csv(config.FACTORS_FILE, parse_dates=["date"], index_col="date")

    # Single-month returns of each cohort name in months t+1..t+12 (cash after an exit), from the cumulative ones.
    cum = np.column_stack([np.zeros(len(e))] + [e[f"fwd_{j}"].to_numpy() for j in range(1, 13)])
    with np.errstate(divide="ignore", invalid="ignore"):
        one = np.where(1 + cum[:, :-1] == 0, 0.0, (1 + cum[:, 1:]) / (1 + cum[:, :-1]) - 1)

    dates = pd.DatetimeIndex(np.sort(e["date"].unique()))
    permnos = np.sort(e["permno"].unique())
    C = np.zeros((len(dates), len(permnos)))            # composite FMP weights by formation
    Rcomp = np.full((len(dates), 12), np.nan)           # composite return in month formation + j
    rows = []
    for s, (t, g) in enumerate(e.groupby("date", sort=True)):
        g = g.dropna(subset=fmp.STYLES)
        X, cols = fmp.design(g, fmp.STYLES)
        P = fmp.fmp_weights(X, np.sqrt(g["mktcap"].to_numpy()))
        y = g["fwd_1"].to_numpy()
        f = P[: len(fmp.STYLES)] @ y
        c = fmp.composite(P, cols)
        idx = g.index.to_numpy()
        C[s, np.searchsorted(permnos, g["permno"].to_numpy())] = c
        Rcomp[s] = [np.sum(c * one[idx, j]) if not np.isnan(one[idx, j]).any() else np.nan for j in range(12)]
        rows.append({"date": t + pd.offsets.MonthEnd(1), "formation": t, "names": len(g),
                     **{st.removesuffix("_z"): fv for st, fv in zip(fmp.STYLES, f)},
                     **{f"gross_leverage_{st.removesuffix('_z')}": np.abs(P[i]).sum() for i, st in enumerate(fmp.STYLES)},
                     "gross_leverage_composite": np.abs(c).sum(), "composite_exposure_check": float(np.abs(c @ X - np.r_[1, 1, 1, np.zeros(X.shape[1] - 3)]).max())})
    fr = pd.DataFrame(rows).set_index("date")
    assert len(fr) == 1152 and fr.index.min() == pd.Timestamp("1929-01-31") and fr.index.max() == pd.Timestamp("2024-12-31")
    assert fr["composite_exposure_check"].max() < 1e-8
    fr.to_csv(out_dir / "factor_returns.csv", date_format="%Y-%m-%d")
    log(f"FMPs: {len(fr)} months; max composite exposure error {fr['composite_exposure_check'].max():.1e}")

    # Paper portfolio: holding month q uses composites formed at q-1..q-K months (formation index q-k+1, horizon k).
    months = fr.index
    paper, metrics = {}, []
    for K in KS:
        for scheme in SCHEMES:
            a = fmp.lag_weights(K, scheme)
            ret = np.full(len(months), np.nan)
            W = np.zeros_like(C)
            for k in range(1, K + 1):
                s_idx = np.arange(len(months)) - k + 1
                ok = s_idx >= 0
                ret[ok] = np.where(np.isnan(ret[ok]), 0, ret[ok]) + a[k - 1] * Rcomp[s_idx[ok], k - 1]
                W[ok] += a[k - 1] * C[s_idx[ok]]
            ret[: K - 1] = np.nan                                          # need all K lags
            to = fmp.turnover_matrix(W)
            to[:K] = np.nan
            key = f"K{K}_{scheme}"
            paper[key] = pd.Series(ret, index=months)
            paper[f"{key}_turnover"] = pd.Series(to, index=months)
            paper[f"{key}_gross_leverage"] = pd.Series(np.abs(W).sum(axis=1), index=months).where(~np.isnan(ret))
            for name, (lo, hi) in PERIODS.items():
                r = paper[key].loc[lo:hi]
                m = fmp.active_metrics(r, bench)
                m.update({"K": K, "weighting": scheme, "period": name,
                          "turnover_one_way_monthly": float(paper[f"{key}_turnover"].loc[lo:hi].mean()),
                          "gross_leverage_mean": float(paper[f"{key}_gross_leverage"].loc[lo:hi].mean())})
                metrics.append(m)
    pp = pd.DataFrame(paper).rename_axis("date")
    pp["benchmark_crsp_vw"] = bench.reindex(pp.index)
    pp.to_csv(out_dir / "paper_portfolio.csv", date_format="%Y-%m-%d")
    cols = ["K", "weighting", "period", "months", "first", "last", "mean_annual", "vol_annual", "cumulative_active", "ir",
            "max_drawdown_active", "skew", "excess_kurtosis", "corr_benchmark", "turnover_one_way_monthly", "gross_leverage_mean"]
    pm = pd.DataFrame(metrics)[cols]
    pm.to_csv(out_dir / "paper_metrics.csv", index=False)
    log(f"paper metrics: {len(pm)} rows")

    # Optional, labeled cross-check: the K = 1 composite on Carhart factors (time series).
    y = pp["K1_equal"].dropna()
    cc = stats.ols(y, fac.reindex(y.index)[stats.MODELS["Carhart"]], 12)
    pd.DataFrame([{"series": "composite FMP, K = 1 (cross-check, not part of 7D-F)", **{k: cc[k] for k in
                  ["alpha_annual", "alpha_t_nw", "alpha_t_ols", "beta_mktrf", "beta_smb", "beta_hml", "beta_umd", "adj_r2", "n"]}}]
                 ).to_csv(out_dir / "carhart_crosscheck.csv", index=False)

    # FMP leverage summary by decade.
    dec = (fr.index.year // 10 * 10).astype(str) + "s"
    lev = fr.groupby(dec)[[c for c in fr.columns if c.startswith("gross_leverage") or c == "names"]].mean()
    lev.loc["all"] = fr[lev.columns].mean()
    lev.rename_axis("decade").to_csv(out_dir / "fmp_leverage.csv")
    pd.DataFrame([{"style": "size", **size_counts}]).to_csv(out_dir / "size_clip_counts.csv", index=False)

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, layout="constrained")
    for K in KS:
        axes[0].plot(months, 100 * pp[f"K{K}_equal"].cumsum(), lw=1.2, label=f"K = {K}, equal")
    for st in ["lowvol", "momentum", "npy", "size"]:
        axes[1].plot(months, 100 * fr[st].cumsum(), lw=1.2, label=st)
    axes[0].set(ylabel="Cumulative active return (%, sum)", title="Paper portfolio from lagged composite FMPs (overlay on CRSP VW, gross)")
    axes[1].set(ylabel="Cumulative factor return (%, sum)", title="Factor returns: unit-exposure FMPs, net of industries and the other styles")
    for ax in axes:
        ax.axhline(0, color="black", lw=0.6)
        ax.legend(fontsize=8, ncol=4)
    fig.savefig(out_dir / "fig_cum.png", dpi=150)
    plt.close(fig)
    log("done: " + ", ".join(sorted(p.name for p in out_dir.iterdir())))
