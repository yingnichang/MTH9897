"""Factor diagnostics 1-7C on CRSP, formations 1928-12 .. 2024-11. Ported unchanged from the closed task
2026-10-11-factor-diagnostics. The security-level universe/exposure/forward-return table goes to
output/diagnostics_universe.parquet (git-ignored), which the FMP, long/short and optimization studies reuse.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from crsp_pipeline import config
from research import diagnostics as dg, engine

NAME = 'diagnostics'
DEPENDS = ()
FIXED_END = "2024-12-31"                       # sample fixed at 2024-12: run_all rejects another --end
FILES = {
    'clip_counts.csv': {'description': 'Values, missing and clipped counts of each neutralized signal, by decade', 'window': 'formations 1928-12 .. 2024-11 (returns to 2024-12)', 'returns': 'n/a', 'role': 'check'},
    'forward_checks.csv': {'description': 'Forward-return checks: missing inside the data window, exits within each horizon', 'window': 'formations 1928-12 .. 2024-11 (returns to 2024-12)', 'returns': 'n/a', 'role': 'check'},
    'ic.csv': {'description': 'Rank IC at h = 1, 3, 6, 12: mean, sd, literal mean/sd, NW t', 'window': 'formations 1928-12 .. 2024-11 (returns to 2024-12)', 'returns': 'gross', 'role': 'primary'},
    'ic_decay.csv': {'description': 'Rank IC by horizon h = 1..12 (decay)', 'window': 'formations 1928-12 .. 2024-11 (returns to 2024-12)', 'returns': 'gross', 'role': 'primary'},
    'ic_monthly.csv': {'description': 'Monthly rank IC series by exposure and horizon', 'window': 'formations 1928-12 .. 2024-11 (returns to 2024-12)', 'returns': 'gross', 'role': 'primary'},
    'persistence.csv': {'description': 'Exposure persistence: rank correlation of exposures at t and t + h', 'window': 'formations 1928-12 .. 2024-11 (returns to 2024-12)', 'returns': 'n/a', 'role': 'primary'},
    'deciles.csv': {'description': 'Decile industry-adjusted returns, hit rates and D10-D1 spreads (literal ER/sd and NW t)', 'window': 'formations 1928-12 .. 2024-11 (returns to 2024-12)', 'returns': 'gross', 'role': 'primary'},
    'deciles_subperiods.csv': {'description': 'Decile results by RS-006 period', 'window': 'formations 1928-12 .. 2024-11 (returns to 2024-12)', 'returns': 'gross', 'role': 'primary'},
    'fig_ic_ma.png': {'description': '12-month moving average of the 1-month rank IC', 'window': 'formations 1928-12 .. 2024-11 (returns to 2024-12)', 'returns': 'gross', 'role': 'primary'},
    'fig_decay.png': {'description': 'IC decay and exposure persistence', 'window': 'formations 1928-12 .. 2024-11 (returns to 2024-12)', 'returns': 'gross', 'role': 'primary'},
    'fig_deciles.png': {'description': 'Decile mean returns at h = 1 and 12', 'window': 'formations 1928-12 .. 2024-11 (returns to 2024-12)', 'returns': 'gross', 'role': 'primary'},
}
FIRST, LAST = pd.Timestamp("1928-12-31"), pd.Timestamp("2024-11-30")
H = list(range(1, 13))
MAIN_H = [1, 3, 6, 12]
PERIOD_NAMES = ["1929–1962", "1963–1989", "1990–2016", "2017–2024"]

def build_universe(ctx):
    """Universe, exposures and forward returns; writes the security-level cache to output/ (git-ignored)."""
    log = ctx.log
    cache = Path(ctx.output) / "diagnostics_universe.parquet"
    cache.parent.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(config.PANEL_FILE)
    sig = engine.attach_signals(panel)
    u = dg.monthly_universe(sig, FIRST, LAST)
    e, counts = dg.exposures(u[["date", "permno", "ff12", "mktcap", "vol36", "momentum", "npy", "ret_hold"]])
    fwd = dg.forward_returns(panel, e, H)
    e = pd.concat([e, fwd], axis=1)
    for h in H:
        e[f"adj_{h}"] = dg.industry_adjust(e[f"fwd_{h}"], e["date"], e["group"])
    first_ret = e["date"] + pd.offsets.MonthEnd(1)
    e["period"] = pd.cut(first_ret.dt.year, [1928, 1962, 1989, 2016, 2024], labels=PERIOD_NAMES).astype(str)
    e.to_parquet(cache, index=False)
    from research.cache import record_universe
    record_universe(ctx, cache)
    log(f"universe: {len(e):,} rows, {e['date'].nunique()} formations ({e['date'].min().date()}..{e['date'].max().date()})")
    return e, panel, counts


def run(ctx):
    out_dir, log = ctx.out(NAME), ctx.log
    e, panel, counts = build_universe(ctx)
    # Data checks: a missing forward return before any exit and inside the data window would be a gap.
    end_ok = {h: e["date"] + pd.offsets.MonthEnd(h) <= panel["date"].max() for h in H}
    gaps = {h: int((e[f"fwd_{h}"].isna() & end_ok[h]).sum()) for h in MAIN_H}
    exits = {h: int(e[f"exit_within_{h}"].sum()) for h in MAIN_H}
    log(f"missing forward returns inside the data window: {gaps}; exits within horizon: {exits}")

    # --- Clip and missing counts -----------------------------------------------------------------------
    decade = (e["date"].dt.year // 10 * 10).astype(str) + "s"
    rows = []
    for s in dg.SIGNALS:
        raw, z = e[s], e[f"{s}_z"]
        d = raw - raw.groupby([e["date"], e["group"]]).transform("mean")
        zz = d / d.groupby(e["date"]).transform(lambda x: x.std(ddof=1))
        for dec, idx in [("all", e.index)] + list(e.groupby(decade).groups.items()):
            rows.append({"signal": s, "decade": dec, "values": int(raw.loc[idx].notna().sum()),
                         "missing": int(raw.loc[idx].isna().sum()), "clipped": int(zz.loc[idx].abs().gt(dg.CLIP).sum())})
    clip = pd.DataFrame(rows)
    assert (clip.loc[clip["decade"].eq("all")].set_index("signal")["clipped"] == counts.set_index("signal").loc[dg.SIGNALS, "clipped"]).all()
    comp = counts.loc[counts["signal"].eq("composite")].iloc[0]
    clip = pd.concat([clip, pd.DataFrame([{"signal": "composite", "decade": "all", "values": comp["values"],
                                           "missing": comp["missing"], "clipped": 0}])], ignore_index=True)
    clip.to_csv(out_dir / "clip_counts.csv", index=False)

    # --- IC, decay, persistence ------------------------------------------------------------------------
    ic_series, ic_rows, decay_rows = {}, [], []
    for x in dg.EXPOSURES:
        for h in H:
            s = dg.spearman_by_date(e, x, f"adj_{h}")
            ic_series[(x, h)] = s
            st = dg.nw_mean(s, lags=h - 1 + 12)
            decay_rows.append({"exposure": x, "h": h, **st})
            if h in MAIN_H:
                ic_rows.append({"exposure": x, "h": h, **st, "first": s.dropna().index.min().date(),
                                "last": s.dropna().index.max().date()})
    pd.DataFrame(ic_rows).to_csv(out_dir / "ic.csv", index=False)
    pd.DataFrame(decay_rows).to_csv(out_dir / "ic_decay.csv", index=False)
    pd.DataFrame({f"{x}|h{h}": s for (x, h), s in ic_series.items() if h in MAIN_H}).rename_axis("date").to_csv(
        out_dir / "ic_monthly.csv", date_format="%Y-%m-%d")
    log("IC done")

    pers_rows = []
    key = e[["date", "permno", *dg.EXPOSURES]]
    for h in H:
        later = key.assign(date=key["date"] - pd.offsets.MonthEnd(h))
        m = key.merge(later, on=["date", "permno"], suffixes=("", "_later"))
        for x in dg.EXPOSURES:
            s = dg.spearman_by_date(m, x, f"{x}_later")
            pers_rows.append({"exposure": x, "h": h, **dg.nw_mean(s, lags=h - 1 + 12),
                              "mean_names_per_date": float(m.groupby("date")[[x, f"{x}_later"]].count().min(axis=1).mean())})
    pd.DataFrame(pers_rows).to_csv(out_dir / "persistence.csv", index=False)
    log("persistence done")

    # --- Deciles -------------------------------------------------------------------------------------------
    def decile_table(frame, label):
        out = []
        for x in dg.EXPOSURES:
            dec = dg.deciles(frame[x], frame["date"], frame["permno"])
            for h in MAIN_H:
                y = frame[f"adj_{h}"]
                per = pd.DataFrame({"date": frame["date"], "dec": dec, "er": y, "hit": (y > 0).where(y.notna())}).dropna()
                g = per.groupby(["date", "dec"]).agg(er=("er", "mean"), hr=("hit", "mean"), n=("er", "size")).reset_index()
                wide = g.pivot(index="date", columns="dec", values="er")
                for d in range(1, 11):
                    s = wide[d].dropna()
                    st = dg.nw_mean(s, lags=h - 1 + 12)
                    out.append({"sample": label, "exposure": x, "h": h, "decile": str(d), "mean_er": st["mean"],
                                "sd_er": st["sd"], "er_over_sd_literal": st["mean_over_sd_literal"], "t_nw": st["t_nw"],
                                "nw_lags": st["nw_lags"], "hit_rate": float(g.loc[g["dec"].eq(d), "hr"].mean()),
                                "mean_names": float(g.loc[g["dec"].eq(d), "n"].mean()), "months": st["months"]})
                spread = (wide[10] - wide[1]).dropna()
                st = dg.nw_mean(spread, lags=h - 1 + 12)
                out.append({"sample": label, "exposure": x, "h": h, "decile": "D10-D1", "mean_er": st["mean"],
                            "sd_er": st["sd"], "er_over_sd_literal": st["mean_over_sd_literal"], "t_nw": st["t_nw"],
                            "nw_lags": st["nw_lags"], "hit_rate": float((spread > 0).mean()), "mean_names": np.nan,
                            "months": st["months"]})
        return pd.DataFrame(out)

    dec_all = decile_table(e, "1929–2024")
    dec_all.to_csv(out_dir / "deciles.csv", index=False)
    dec_sub = pd.concat([decile_table(e.loc[e["period"].eq(p)], p) for p in PERIOD_NAMES], ignore_index=True)
    dec_sub.to_csv(out_dir / "deciles_subperiods.csv", index=False)
    log("deciles done")

    # --- Figures ----------------------------------------------------------------------------------------
    names = {"lowvol_z": "Low volatility", "momentum_z": "Momentum (12-1)", "npy_z": "Net payout yield", "composite_z": "Composite"}
    fig, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True, layout="constrained")
    for ax, x in zip(axes, dg.EXPOSURES):
        s = ic_series[(x, 1)]
        ax.plot(s.index, s.rolling(12).mean(), color="#176B87", lw=1.1)
        ax.axhline(0, color="black", lw=0.6)
        ax.axhline(s.mean(), color="#C0504D", lw=0.8, ls="--")
        ax.set_ylabel(names[x], fontsize=9)
    axes[0].set_title("1-month rank IC with industry-adjusted forward returns: 12-month moving average (dashed: full-sample mean)", fontsize=10)
    fig.savefig(out_dir / "fig_ic_ma.png", dpi=150)
    plt.close(fig)

    dec = pd.DataFrame(decay_rows)
    pr = pd.DataFrame(pers_rows)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
    for x in dg.EXPOSURES:
        axes[0].plot(H, dec.loc[dec["exposure"].eq(x), "mean"], marker="o", label=names[x])
        axes[1].plot(H, pr.loc[pr["exposure"].eq(x), "mean"], marker="o", label=names[x])
    axes[0].set(xlabel="Horizon h (months)", ylabel="Mean rank IC", title="IC decay")
    axes[1].set(xlabel="Lag h (months)", ylabel="Mean rank correlation of exposures", title="Exposure persistence")
    axes[0].axhline(0, color="black", lw=0.6)
    axes[0].legend(fontsize=8)
    fig.savefig(out_dir / "fig_decay.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(2, 4, figsize=(14, 6), sharey="row", layout="constrained")
    for j, x in enumerate(dg.EXPOSURES):
        for i, h in enumerate([1, 12]):
            r = dec_all.loc[dec_all["exposure"].eq(x) & dec_all["h"].eq(h) & dec_all["decile"].ne("D10-D1")]
            axes[i, j].bar(r["decile"].astype(int), 100 * r["mean_er"], color="#176B87")
            axes[i, j].axhline(0, color="black", lw=0.6)
            axes[i, j].set_title(f"{names[x]}, h = {h}", fontsize=9)
            axes[i, j].set_xticks(range(1, 11))
        axes[1, j].set_xlabel("Decile (10 = highest exposure)")
    axes[0, 0].set_ylabel("Mean industry-adjusted return, % per h months")
    axes[1, 0].set_ylabel("Mean industry-adjusted return, % per h months")
    fig.savefig(out_dir / "fig_deciles.png", dpi=150)
    plt.close(fig)
    pd.DataFrame([{"check": "missing forward return inside data window", **{f"h{h}": v for h, v in gaps.items()}},
                  {"check": "exit within horizon", **{f"h{h}": v for h, v in exits.items()}}]).to_csv(out_dir / "forward_checks.csv", index=False)
    log("done: " + ", ".join(sorted(p.name for p in out_dir.iterdir())))
