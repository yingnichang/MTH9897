"""LaTeX table bodies for the HW2 report, written to report/tables/ from the notebook's saved outputs.

Run from the HW2 folder:  python report/make_tables.py

Every number in the report's tables comes from output/*.csv (seed 0 for simulations) or data/paper/*.csv;
captions and prose live in report.tex.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

HW2 = Path(__file__).resolve().parents[1]
OUTPUT, PAPER, TABLES = HW2 / "output", HW2 / "data" / "paper", HW2 / "report" / "tables"
MONTHLY_SIGMAS = [round(0.02 * k, 2) for k in range(11)]
DAILY_SIGMAS = [round(0.0045 * k, 4) for k in range(11)]


def read(name, folder=OUTPUT):
    return pd.read_csv(folder / f"{name}.csv", float_precision="round_trip")


def num(x, dp=1, scale=1.0, sign=False):
    """Number for LaTeX: thousands separators, a true minus sign, '--' for missing."""
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "--"
    text = f"{abs(x) * scale:,.{dp}f}"
    if float(text.replace(",", "")) == 0:
        return text
    return ("$-$" if x < 0 else ("+" if sign else "")) + text


def pct(x, dp=1):
    return num(x, dp, 100)


def skew(x):
    """Skewness with about three significant digits."""
    if not np.isfinite(x):
        return "--"
    return num(x, 2 if abs(x) < 10 else 1 if abs(x) < 100 else 0)


def big_pct(x):
    """Returns that can reach thousands of percent: whole percent from 1,000%."""
    return pct(x, 0 if abs(x) >= 10 else 1)


def write(name, lines):
    TABLES.mkdir(parents=True, exist_ok=True)
    (TABLES / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def seed0(name):
    frame = read(name)
    frame = frame[frame["seed"] == 0]
    if frame.duplicated(["horizon_years", "sigma"]).any():
        raise ValueError(f"{name}: more than one seed-0 row per cell")
    return frame.set_index(["horizon_years", "sigma"])


# ---------------------------------------------------------------------------------------------------------
# Simulated multi-period returns (Table 1)
# ---------------------------------------------------------------------------------------------------------
def sigma_header(sigmas, daily):
    cells = [num(s, 2, 100) if daily else num(s, 0, 100) for s in sigmas]
    return " & ".join(cells)


def table1_daily():
    """The paper's Table 1 layout with daily draws at a mean of 0.0025% a day (seed 0)."""
    daily = seed0("table1_daily_assigned")
    stats = [("skew", "Skewness", skew), ("median", "Median (\\%)", pct),
             ("pct_positive", "\\% $>0$", pct), ("p99", "99th pct.\\ (\\%)", big_pct)]
    lines = [r"\begin{tabular}{@{}ll" + "r" * 11 + "@{}}", r"\toprule",
             r" & & \multicolumn{11}{c}{Daily $\sigma$ (\%)} \\ \cmidrule(l){3-13}",
             r"Statistic & Horizon & " + sigma_header(DAILY_SIGMAS, True) + r" \\",
             r"& & \multicolumn{11}{c}{\textit{paired monthly column in the paper (\%)}} \\",
             r"& & " + sigma_header(MONTHLY_SIGMAS, False) + r" \\ \midrule"]
    for k, (stat, label, fmt) in enumerate(stats):
        for j, years in enumerate((1.0, 5.0, 10.0)):
            cells = [fmt(daily.loc[(years, s), stat]) for s in DAILY_SIGMAS]
            lines.append((label if j == 0 else "") + f" & {years:.0f}y & " + " & ".join(cells) + r" \\")
        if k < len(stats) - 1:
            lines.append(r"\addlinespace")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("table1_daily", lines)


def table1_compare():
    """Comparison with Table 1 at 10 years: the paper, our monthly replication and both daily versions."""
    paper = read("table1", PAPER).set_index(["stat", "horizon_years", "sigma"])["value"]
    runs = [("Paper, monthly", None, MONTHLY_SIGMAS),
            ("Ours, monthly", seed0("table1_monthly"), MONTHLY_SIGMAS),
            ("Ours, daily, $\\mu = 0.0025\\%$", seed0("table1_daily_assigned"), DAILY_SIGMAS),
            ("Ours, daily, matched $\\mu$", seed0("table1_daily_matched"), DAILY_SIGMAS)]
    lines = [r"\begin{tabular}{@{}ll" + "r" * 11 + "@{}}", r"\toprule",
             r"& Monthly $\sigma$ (\%) & " + sigma_header(MONTHLY_SIGMAS, False) + r" \\",
             r"& Daily $\sigma$ (\%) & " + sigma_header(DAILY_SIGMAS, True) + r" \\ \midrule"]
    for k, (stat, label) in enumerate((("median", "Median (\\%)"), ("pct_positive", "\\% $>0$"))):
        for j, (name, frame, sigmas) in enumerate(runs):
            if frame is None:
                cells = [pct(paper.loc[(stat, 10, s)]) for s in MONTHLY_SIGMAS]
            else:
                cells = [pct(frame.loc[(10.0, s), stat]) for s in sigmas]
            lines.append((label if j == 0 else "") + f" & {name} & " + " & ".join(cells) + r" \\")
        if k == 0:
            lines.append(r"\addlinespace")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("table1_compare", lines)


def table1_long():
    """Horizons of 15 and 20 years with the paper's monthly parameters (seed 0), plus the exact skewness."""
    long = seed0("table1_monthly_15_20y")
    stats = [("skew", "Skewness, sample", skew), ("unclipped_exact_skew", "Skewness, exact", skew),
             ("median", "Median (\\%)", pct), ("pct_positive", "\\% $>0$", pct),
             ("p99", "99th pct.\\ (\\%)", big_pct)]
    lines = [r"\begin{tabular}{@{}ll" + "r" * 11 + "@{}}", r"\toprule",
             r" & & \multicolumn{11}{c}{Monthly $\sigma$ (\%)} \\ \cmidrule(l){3-13}",
             r"Statistic & Horizon & " + sigma_header(MONTHLY_SIGMAS, False) + r" \\ \midrule"]
    for k, (stat, label, fmt) in enumerate(stats):
        for j, years in enumerate((15.0, 20.0)):
            cells = [fmt(long.loc[(years, s), stat]) for s in MONTHLY_SIGMAS]
            lines.append((label if j == 0 else "") + f" & {years:.0f}y & " + " & ".join(cells) + r" \\")
        if k < len(stats) - 1:
            lines.append(r"\addlinespace")
    mean = [big_pct(long.loc[(20.0, s), "unclipped_exact_mean"]) for s in MONTHLY_SIGMAS]
    lines += [r"\addlinespace", r"Mean, exact (\%) & 20y & " + " & ".join(mean) + r" \\",
              r"\bottomrule", r"\end{tabular}"]
    write("table1_long", lines)


# ---------------------------------------------------------------------------------------------------------
# Industry portfolios (Table 4)
# ---------------------------------------------------------------------------------------------------------
STAT_NAMES = {"mean": "Mean (\\%)", "median": "Median (\\%)", "skew": "Skewness", "pct_positive": "\\% $>0$",
              "pct_above_tbill": "\\% $>$ T-bill", "pct_above_vw": "\\% $>$ VW market"}


def table4():
    """Random industry selection in the paper's Table 4 layout, next to the paper's portfolios."""
    frame = read("table4_random_vs_paper")
    columns = ["FF49 EW", "FF49 VW", "FF12 EW", "FF12 VW"] + [f"paper, {n} stock" + ("s" if n > 1 else "")
                                                              for n in (1, 5, 25, 50, 100)]
    lines = [r"\begin{tabular}{@{}ll" + "r" * 9 + "@{}}", r"\toprule",
             r"& & \multicolumn{4}{c}{Random industry (ours)} & \multicolumn{5}{c}{Random stocks (paper)} \\",
             r"\cmidrule(lr){3-6} \cmidrule(l){7-11}",
             r"Horizon & Statistic & FF49 EW & FF49 VW & FF12 EW & FF12 VW & 1 & 5 & 25 & 50 & 100 \\ \midrule"]
    horizons = {"1-year": "1 year", "10-year": "10 years", "full period": "Full period"}
    for k, (horizon, label) in enumerate(horizons.items()):
        part = frame[frame["horizon"] == horizon].set_index("statistic")
        for j, stat in enumerate(STAT_NAMES):
            values = part.loc[stat, columns].astype(float)
            if stat == "skew":  # two decimals, as in the paper's Table 4
                cells = [num(v, 2) for v in values]
            elif stat in ("mean", "median") and horizon == "full period":
                cells = [big_pct(v) for v in values]
            else:
                cells = [pct(v, 2) for v in values]
            if stat == "pct_above_vw":
                cells = [r"\textbf{" + c + "}" for c in cells]
            lines.append((label if j == 0 else "") + f" & {STAT_NAMES[stat]} & " + " & ".join(cells) + r" \\")
        if k < len(horizons) - 1:
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("table4_random", lines)


VARIANTS = ["FF49 EW", "FF49 VW", "FF12 EW", "FF12 VW"]


def momentum():
    """Three-month momentum against the random paths (full period and window win rates)."""
    versus = read("table4_momentum_vs_random").set_index(["horizon", "statistic"])
    performance = read("table4_momentum_performance").set_index("strategy")
    windows = read("table4_momentum_windows").query("kind == 'full'")
    lines = [r"\begin{tabular}{@{}lrrrlrrr@{}}", r"\toprule",
             r"& \multicolumn{3}{c}{Wealth per \$1} & Percentile & "
             r"\multicolumn{3}{c}{\% of windows $>$ VW market} \\",
             r"\cmidrule(lr){2-4} \cmidrule(l){6-8}",
             r"Variant & Momentum & Random median & Random mean & [95\% CI] & Years & Decades & "
             r"Rolling 10y \\ \midrule"]
    for v in VARIANTS:
        universe, weighting = v.lower().split()
        row = windows.query("universe == @universe and weighting == @weighting").iloc[0]
        cells = [num(performance.loc[f"Momentum, {v}", "terminal wealth"], 0),
                 num(1 + versus.loc[("full period", "median"), f"{v}: random"], 0),
                 num(performance.loc[f"Equal weight across industries, {v}", "terminal wealth"], 0),
                 f"{pct(row['percentile'], 2)} [{pct(row['wilson_low'], 2)}, {pct(row['wilson_high'], 2)}]"]
        for horizon in ("1-year", "10-year", "rolling 10-year"):
            mom, rnd = (versus.loc[(horizon, "pct_above_vw"), f"{v}: {who}"] for who in ("momentum", "random"))
            cells.append(f"{pct(mom)} / {pct(rnd)}")
        lines.append(f"{v} & " + " & ".join(cells) + r" \\")
    market = performance.loc["VW market", "terminal wealth"]
    tbill = performance.loc["T-bills", "terminal wealth"]
    lines += [r"\midrule", f"VW market & {num(market, 0)} & & & & & & \\\\",
              f"T-bills & {num(tbill, 0)} & & & & & & \\\\", r"\bottomrule", r"\end{tabular}"]
    write("momentum", lines)


def performance_rows(frame, label_column, turnover=True):
    rows = []
    for _, r in frame.iterrows():
        drawdown = pct(r["max drawdown"])
        if isinstance(r["drawdown peak"], str):
            drawdown += f" ({r['drawdown peak']} to {r['drawdown trough']})"
        cells = [num(r["terminal wealth"], 0 if r["terminal wealth"] >= 100 else 2), pct(r["annualized return"]),
                 pct(r["annualized volatility"]), num(r["Sharpe ratio"], 2), drawdown]
        if turnover:
            cells.append("--" if pd.isna(r["annual turnover"]) else pct(r["annual turnover"], 0))
        rows.append(cells)
    return rows


def momentum_performance():
    frame = read("table4_momentum_performance")
    names = {"VW market": "VW market", "T-bills": "T-bills"}
    lines = [r"\begin{tabular}{@{}lrrrrlr@{}}", r"\toprule",
             r"Strategy & Wealth & Return & Volatility & Sharpe & Max drawdown (peak to trough) & Turnover \\",
             r"\midrule"]
    for (_, r), cells in zip(frame.iterrows(), performance_rows(frame, "strategy")):
        name = names.get(r["strategy"], r["strategy"].replace("Equal weight across industries", "Equal weight"))
        if r["strategy"] == "Equal weight across industries, FF49 EW":
            lines.append(r"\midrule")
        if r["strategy"] == "VW market":
            lines.append(r"\midrule")
        lines.append(f"{name} & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("momentum_performance", lines)


def rule_screen():
    frame = read("table4_bonus_screen")
    lines = [r"\begin{tabular}{@{}lrrrrr@{}}", r"\toprule",
             r"& & \multicolumn{2}{c}{(a) equal weight} & \multicolumn{2}{c}{(b) top 5, 6-month} \\",
             r"\cmidrule(lr){3-4} \cmidrule(l){5-6}",
             r"Measure & Windows & Wins & Win rate & Wins & Win rate \\ \midrule"]
    for k, r in frame.iterrows():
        measure = re.sub(r"(\d{4})-(\d{4})", r"\1--\2", r["measure"]).replace("(screen)", r"\textbf{(screen)}")
        cells = [num(r["windows"], 0), num(r["a: wins"], 0), pct(r["a: win rate"]) + r"\%",
                 num(r["b: wins"], 0), pct(r["b: win rate"]) + r"\%"]
        lines.append(f"{measure} & " + " & ".join(cells) + r" \\")
        if k == 1:
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("rule_screen", lines)


def rule_performance():
    frame = read("table4_bonus_performance")
    rules = {"(a) equal weight across industries": "(a) equal weight", "(b) top 5 by six-month return": "(b) top 5",
             "VW market": "VW market"}
    lines = [r"\begin{tabular}{@{}llrrrrrr@{}}", r"\toprule",
             r"Period & Strategy & Wealth & Return & Volatility & Sharpe & Max drawdown & Turnover \\ \midrule"]
    rows = performance_rows(frame.assign(**{"drawdown peak": np.nan}), "strategy")
    previous = None
    for (_, r), cells in zip(frame.iterrows(), rows):
        period = r["period"].split(": ")[1].replace(" to ", "--")
        if previous is not None and period != previous:
            lines.append(r"\addlinespace")
        lines.append((period if period != previous else "") + f" & {rules[r['strategy']]} & "
                     + " & ".join(cells) + r" \\")
        previous = period
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("rule_performance", lines)


if __name__ == "__main__":
    for build in (table1_daily, table1_compare, table1_long, table4, momentum, momentum_performance, rule_screen,
                  rule_performance):
        build()
    print("wrote", ", ".join(sorted(p.name for p in TABLES.glob("*.tex"))))
