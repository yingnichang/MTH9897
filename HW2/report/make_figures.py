"""Print-size figures for the HW2 report, written to report/figures/ as vector PDFs.

Run from the HW2 folder:  python report/make_figures.py   (about 1 minute)

Table 1 figures read the cached simulations in output/ (seed 0). Table 4 figures rebuild the random-industry
paths (seed 0, 20,000 paths) from src/ and read the saved momentum and market-beating-rule exports. Each input is checked against
the saved outputs before plotting, so the figures cannot drift from the notebook's numbers.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, PercentFormatter
from matplotlib.transforms import offset_copy

HW2 = Path(__file__).resolve().parents[1]
OUTPUT, FIGURES = HW2 / "output", HW2 / "report" / "figures"
sys.path.insert(0, str(HW2 / "src"))

from ff_data import formation_eligibility, load_all, verify_cache  # noqa: E402
from table4_eval import full_period, window_wealth  # noqa: E402
from table4_strategies import random_selections, selected_returns  # noqa: E402

# Palette and anatomy follow the notebook (validated with the dataviz skill's validator on a white surface).
INK, INK_2, MUTED, GRID, BASE, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#ffffff"
HORIZON_COLORS = {1: "#86b6ef", 5: "#5598e7", 10: "#2a78d6", 15: "#1c5cab", 20: "#104281"}
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
WIDTH = 6.5  # inches: the report's text width

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "legend.fontsize": 7.5, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": BASE, "axes.labelcolor": INK_2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.titlecolor": INK, "axes.titlelocation": "left", "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.5, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "legend.labelcolor": INK_2, "pdf.fonttype": 42,
})


def require(ok, message):
    if not ok:
        raise ValueError(f"figure input does not match the saved outputs: {message}")


def spread(values, gap, iterations=500):
    """Push label positions apart until neighbours are at least `gap` apart, keeping their centre."""
    order = np.argsort(values)
    pos = np.asarray(values, dtype=float)[order]
    for _ in range(iterations):
        overlaps = gap - np.diff(pos)
        if (overlaps <= 1e-12).all():
            break
        for i in np.flatnonzero(overlaps > 1e-12):
            pos[i] -= overlaps[i] / 2
            pos[i + 1] += overlaps[i] / 2
    out = np.empty_like(pos)
    out[order] = pos
    return out


def label_ends(ax, ends, gap_points=8, log=False, dx_points=5):
    """Direct-label line ends (x, y, text); colliding labels are spread apart with a thin leader."""
    fig = ax.figure
    fig.canvas.draw()
    height = ax.get_window_extent().height * 72 / fig.dpi
    low, high = ax.get_ylim()
    ys = np.array([y for _, y, _ in ends], dtype=float)
    if log:
        low, high, ys = np.log10(low), np.log10(high), np.log10(ys)
    gap = gap_points * (high - low) / height
    placed = spread(ys, gap)
    text_at = offset_copy(ax.transData, fig=fig, x=dx_points, units="points")
    for (x, y, text), y_label, y_raw in zip(ends, placed, ys):
        x = mdates.date2num(x) if isinstance(x, pd.Timestamp) else x  # offset transforms skip unit conversion
        leader = dict(arrowstyle="-", color=MUTED, linewidth=0.5, shrinkA=0, shrinkB=1) \
            if abs(y_label - y_raw) > gap / 4 else None
        ax.annotate(text, xy=(x, y), xytext=(x, 10**y_label if log else y_label), textcoords=text_at,
                    va="center", fontsize=7, color=INK_2, arrowprops=leader, annotation_clip=False)


# ---------------------------------------------------------------------------------------------------------
# Table 1: median and share positive against volatility (Table 1 with normal returns)
# ---------------------------------------------------------------------------------------------------------
def seed0(name):
    frame = pd.read_csv(OUTPUT / f"{name}.csv", float_precision="round_trip")
    return frame[frame["seed"] == 0]


def table1_figure():
    monthly = pd.concat([seed0("table1_monthly"), seed0("table1_monthly_15_20y")])
    panels = [("Monthly, μ = 0.5% (paper)", monthly, 0.005, 12, "monthly σ"),
              ("Daily, μ = 0.0025%", seed0("table1_daily_assigned"), 0.000025, 252, "daily σ"),
              ("Daily, μ = 0.0238% (matched)", seed0("table1_daily_matched"), 1.005 ** (1 / 21) - 1, 252, "daily σ")]
    for _, frame, *_ in panels:
        require(frame.groupby(["horizon_years", "sigma"]).size().eq(1).all(), "one seed-0 row per cell")
    # y-limits leave room below the data for the spread end labels of the five monthly horizons.
    rows = [("median", "median buy-and-hold return", 0.0, True, (-1.35, 2.45)),
            ("pct_positive", "share of returns > 0", 0.5, False, (0.0, 1.04))]

    fig, axes = plt.subplots(2, 3, figsize=(WIDTH, 4.3), sharey="row")
    for r, (stat, ylabel, reference, approximation, ylim) in enumerate(rows):
        for c, (title, frame, mu, per_year, xlabel) in enumerate(panels):
            ax = axes[r, c]
            ax.axhline(reference, color=BASE, linewidth=0.8, zorder=1)
            ends = []
            for years, group in frame.groupby("horizon_years"):
                group = group.sort_values("sigma")
                color = HORIZON_COLORS[int(round(years))]
                ax.plot(group["sigma"], group[stat], color=color, linewidth=1.4, marker="o", markersize=2.5,
                        zorder=3, label=f"{years:.0f} year" + ("" if round(years) == 1 else "s"))
                if approximation:  # lognormal intuition: median ≈ exp(T(μ − σ²/2)) − 1
                    grid = np.linspace(0, group["sigma"].max(), 100)
                    ax.plot(grid, np.exp(years * per_year * (mu - grid**2 / 2)) - 1, color=color, linewidth=0.7,
                            linestyle=(0, (3, 2)), alpha=0.8, zorder=2)
                last = group.iloc[-1]
                ends.append((last["sigma"], last[stat], f"{years:.0f}y"))
            if r == 0:
                ax.set_title(title)
            ax.set_xlabel(xlabel)
            ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
            ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
            ax.margins(x=0.04)
            ax.set_xlim(right=ax.get_xlim()[1] + 0.12 * (ax.get_xlim()[1] - ax.get_xlim()[0]))
            ax.set_ylim(*ylim)
            ax._ends = ends
        axes[r, 0].set_ylabel(ylabel)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    handles.append(plt.Line2D([], [], color=MUTED, linewidth=0.7, linestyle=(0, (3, 2))))
    labels.append("exp(T(μ − σ²/2)) − 1")
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), bbox_to_anchor=(0.5, 1.0),
               handlelength=1.8, columnspacing=1.2)
    fig.tight_layout(rect=(0, 0, 1, 0.95), h_pad=0.8, w_pad=0.6)
    for ax in axes.flat:
        label_ends(ax, ax._ends)
    fig.savefig(FIGURES / "fig_table1.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------------------------------------
# Table 4: rebuild the random-industry paths (seed 0) and check them against the saved exports
# ---------------------------------------------------------------------------------------------------------
VARIANTS = [("ff49", "ew"), ("ff49", "vw"), ("ff12", "ew"), ("ff12", "vw")]
NAMES = {v: f"Random {v[0].upper()} industry, {v[1].upper()} stocks" for v in VARIANTS}


def random_paths():
    industries, factors = load_all(verify_cache())
    bench = factors.loc["1926-07":"2016-12"]
    pooled = pd.read_csv(OUTPUT / "table4_random_pooled.csv", float_precision="round_trip").set_index(
        ["universe", "weighting", "kind"])
    versus = pd.read_csv(OUTPUT / "table4_momentum_vs_random.csv", float_precision="round_trip").set_index(
        ["horizon", "statistic"])
    market = float(np.prod(1 + bench["mkt"]))
    full_wealth, fan = {}, {}
    for key in ("ff49", "ff12"):
        eligible = formation_eligibility(industries[key].firms).loc[bench.index]
        selections = random_selections(eligible, 20_000, 0)
        for weighting in ("ew", "vw"):
            paths = selected_returns(getattr(industries[key], weighting).loc[bench.index], eligible, selections)
            wealth = window_wealth(paths, full_period(bench.index))[0]
            saved = pooled.loc[(key, weighting, "full"), "pct_above_vw"]
            require(abs((wealth > market).mean() - saved) < 1e-12, f"{key} {weighting} share above the market")
            full_wealth[key, weighting] = wealth
            if key == "ff49":  # momentum band: the same draws from October 1926
                log_wealth = np.cumsum(np.log1p(paths.loc["1926-10":].to_numpy()), axis=0)
                fan[key, weighting] = np.exp(np.percentile(log_wealth, [5, 50, 95], axis=1))
                median = 1 + versus.loc[("full period", "median"), f"FF49 {weighting.upper()}: random"]
                require(abs(fan[key, weighting][1, -1] / median - 1) < 1e-3, f"{weighting} random median wealth")
    return full_wealth, fan, market, float(np.prod(1 + bench["rf"])), factors


def random_industry_figure(full_wealth, market, tbill):
    fig, ax = plt.subplots(figsize=(WIDTH, 2.6))
    for v, color in zip(VARIANTS, SLOTS):
        wealth = np.sort(full_wealth[v])
        above = 1 - np.arange(1, len(wealth) + 1) / len(wealth)  # share of paths strictly above each value
        keep = np.unique(np.r_[np.arange(0, len(wealth), 10), len(wealth) - 1])
        ax.plot(wealth[keep], above[keep], color=color, linewidth=1.4, label=NAMES[v], zorder=3)
    for x, text in ((tbill, f"T-bills {tbill:,.0f}×"), (market, f"VW market {market:,.0f}×")):
        ax.axvline(x, color=INK_2, linewidth=0.8, zorder=2)
        ax.annotate(text, xy=(x, 0), xytext=(-3, 3), textcoords="offset points", ha="right", va="bottom",
                    fontsize=7, color=INK_2)
    shares = sorted(((float((full_wealth[v] > market).mean()), v) for v in VARIANTS))
    label_y, last = [], -1.0
    for share, _ in shares:
        last = max(share, last + 0.08)
        label_y.append(last)
    for (share, v), y in zip(shares, label_y):
        color = SLOTS[VARIANTS.index(v)]
        ax.plot(market, share, "o", markersize=5, color=color, markeredgecolor=SURFACE, markeredgewidth=1.2,
                zorder=4)
        ax.annotate(f"{share:.1%}", xy=(market, share), xytext=(market * 1.45, y), fontsize=7, color=INK,
                    va="center", arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.5, shrinkA=0, shrinkB=3))
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:,.0f}×"))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_ylim(0, 1.04)
    ax.set_xlabel("wealth in December 2016 per $1 invested in July 1926 (log scale)")
    ax.set_ylabel("share of paths ending above")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_random_industry.pdf")
    plt.close(fig)


def momentum_figure(fan, factors):
    monthly = pd.read_csv(OUTPUT / "table4_momentum_monthly.csv", float_precision="round_trip")
    performance = pd.read_csv(OUTPUT / "table4_momentum_performance.csv").set_index("strategy")
    bench = factors.loc["1926-10":"2016-12"]
    dates = bench.index.to_timestamp()
    market = np.cumprod(1 + bench["mkt"].to_numpy())
    fig, axes = plt.subplots(2, 1, figsize=(WIDTH, 3.5), sharex=True, sharey=True)
    for ax, weighting in zip(axes, ("ew", "vw")):
        held = monthly.query("universe == 'ff49' and weighting == @weighting")
        require(list(held["month"]) == [str(m) for m in bench.index], f"{weighting} momentum months")
        path = np.cumprod(1 + held["return"].to_numpy())
        saved = performance.loc[f"Momentum, FF49 {weighting.upper()}", "terminal wealth"]
        require(abs(path[-1] / saved - 1) < 1e-9, f"{weighting} momentum terminal wealth")
        low, mid, high = fan["ff49", weighting]
        ax.fill_between(dates, low, high, color=GRID, linewidth=0, zorder=1,
                        label="random paths, 5th–95th percentile")
        ax.plot(dates, mid, color=MUTED, linewidth=1.0, zorder=2, label="random paths, median")
        ax.plot(dates, market, color=SLOTS[1], linewidth=1.3, zorder=3, label="VW market")
        ax.plot(dates, path, color=SLOTS[0], linewidth=1.3, zorder=4, label="momentum")
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:,.0f}×" if x >= 1 else f"{x:g}×"))
        ax.set_title(f"FF49 industries, {weighting.upper()} returns")
        ax.set_yticks([0.01, 1, 100, 10_000])
        ax.yaxis.set_minor_locator(plt.NullLocator())
        ax.xaxis.set_major_locator(mdates.YearLocator(10))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.set_xlim(dates[0], dates[-1] + pd.Timedelta(days=9500))
        ax.set_ylabel("wealth per $1 (log)")
        ax._ends = [(dates[-1], path[-1], f"momentum {path[-1]:,.0f}×"),
                    (dates[-1], market[-1], f"market {market[-1]:,.0f}×"),
                    (dates[-1], mid[-1], f"random median {mid[-1]:,.0f}×")]
    axes[1].set_xticks([pd.Timestamp(f"{year}-01-01") for year in range(1930, 2020, 10)])
    handles, labels = axes[0].get_legend_handles_labels()
    order = [labels.index(n) for n in ("momentum", "VW market", "random paths, median",
                                       "random paths, 5th–95th percentile")]
    fig.legend([handles[i] for i in order], [labels[i] for i in order], loc="upper center", ncol=4,
               bbox_to_anchor=(0.5, 1.0), handlelength=1.8)
    fig.tight_layout(rect=(0, 0, 1, 0.95), h_pad=0.8)
    for ax in axes:
        label_ends(ax, ax._ends, gap_points=8, log=True, dx_points=3)
    fig.savefig(FIGURES / "fig_momentum.pdf")
    plt.close(fig)


def rules_figure():
    windows = pd.read_csv(OUTPUT / "table4_bonus_windows.csv", float_precision="round_trip")
    screen = pd.read_csv(OUTPUT / "table4_bonus_screen.csv").set_index("measure")
    names = {"a": "(a) equal weight across FF49 industries", "b": "(b) top 5 FF49 industries by 6-month return"}
    fig, ax = plt.subplots(figsize=(WIDTH, 2.35))
    first_holdout_end = pd.Period("2005-12", "M").to_timestamp()
    ends = []
    for rule, color in zip(names, SLOTS):
        part = windows.query("rule == @rule and kind == 'rolling120'")
        require(int(part["pct_above_vw"].sum()) == screen.loc["All rolling 10-year windows", f"{rule}: wins"],
                f"rule ({rule}) rolling wins")
        ratio = (1 + part["mean"].to_numpy()) / (1 + part["market"].to_numpy())
        x = pd.PeriodIndex(part["end"], freq="M").to_timestamp()
        ax.plot(x, ratio, color=color, linewidth=1.2, zorder=3, label=names[rule])
        ends.append((x[-1], ratio[-1], f"({rule}) {ratio[-1]:.2f}×"))
    ax.axvspan(first_holdout_end, x[-1], color=GRID, alpha=0.6, linewidth=0, zorder=0,
               label="windows entirely in the 1996–2026 holdout")
    ax.axhline(1.0, color=INK_2, linewidth=0.8, zorder=1)
    ax.set_yscale("log")
    ax.set_ylim(0.4, 8)  # headroom above the 1975-1983 peaks for the legend
    ax.set_yticks([0.5, 0.75, 1, 1.5, 2, 3, 4])
    ax.yaxis.set_minor_locator(plt.NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}×"))
    ax.set_ylabel("rule wealth / market wealth (log)")
    ax.set_xlabel("end of the 10-year window")
    ax.xaxis.set_major_locator(mdates.YearLocator(10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(right=x[-1] + pd.Timedelta(days=2600))
    ax.legend(loc="upper left")
    fig.tight_layout()
    label_ends(ax, ends, gap_points=8, log=True, dx_points=3)
    fig.savefig(FIGURES / "fig_rules.pdf")
    plt.close(fig)


if __name__ == "__main__":
    FIGURES.mkdir(parents=True, exist_ok=True)
    table1_figure()
    full_wealth, fan, market, tbill, factors = random_paths()
    random_industry_figure(full_wealth, market, tbill)
    momentum_figure(fan, factors)
    rules_figure()
    print("wrote", ", ".join(sorted(p.name for p in FIGURES.glob("*.pdf"))))
