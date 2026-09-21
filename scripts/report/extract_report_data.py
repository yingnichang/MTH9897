"""Execute notebook code, export report data, and render report charts."""

import contextlib
import io
import json
import os
from pathlib import Path

os.environ["MPLBACKEND"] = "Agg"

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = ROOT / "tmp" / "pdfs"
BUILD_DIR.mkdir(parents=True, exist_ok=True)


def quiet_display(*_args, **_kwargs):
    return None


def execute_notebook():
    notebook = json.loads((ROOT / "bond_relative_value_assignment.ipynb").read_text(encoding="utf-8"))
    scope = {"__name__": "__main__", "display": quiet_display}
    with contextlib.redirect_stdout(io.StringIO()):
        for cell in notebook["cells"]:
            if cell.get("cell_type") != "code":
                continue
            source = "".join(cell.get("source", []))
            source = source.replace(
                "from IPython.display import Markdown, display",
                "from IPython.display import Markdown",
            )
            source = source.replace(
                'DATA_DIR = Path("data")',
                'DATA_DIR = Path("data") if (Path("data") / "WRDS_Data-Systematic_Trading-Fall2026-1.csv").exists() else Path(".")',
            )
            exec(compile(source, str(ROOT / "bond_relative_value_assignment.ipynb"), "exec"), scope)
            scope["display"] = quiet_display
            if "plt" in scope:
                scope["plt"].show = lambda: None
    return scope


def records(frame):
    rows = []
    for row in frame.reset_index().to_dict(orient="records"):
        clean = {}
        for key, value in row.items():
            if isinstance(value, (pd.Timestamp, np.datetime64)):
                clean[key] = pd.Timestamp(value).isoformat()
            elif isinstance(value, np.integer):
                clean[key] = int(value)
            elif isinstance(value, (np.floating, float)):
                clean[key] = None if not np.isfinite(value) else float(value)
            else:
                clean[key] = value
        rows.append(clean)
    return rows


def savefig(fig, name):
    fig.savefig(BUILD_DIR / name, dpi=190, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    scope = execute_notebook()
    filtered = scope["filtered"]
    filtered_unchecked = scope["filtered_unchecked"]
    exclusions = scope["price_mark_exclusions"]
    model_stats = scope["model_stats"]
    plot_df = scope["plot_df"]
    trial_outputs = scope["trial_outputs"]
    trial_summary = scope["trial_summary"]
    raw_trial_summary = scope["raw_trial_summary"]
    issuer_month_returns = scope["issuer_month_returns"]
    combined_returns = scope["combined_returns"]
    summary_table = scope["summary_table"]
    cost_sensitivity = scope["cost_sensitivity"]
    robustness_table = scope["robustness_table"]
    characteristics = scope["characteristic_comparison"]
    analysis_date = scope["analysis_date"]

    sample_summary = filtered.groupby("company_symbol").agg(
        observations=("ISSUE_ID", "size"),
        unique_bonds=("ISSUE_ID", "nunique"),
        median_duration=("DURATION", "median"),
        duration_min=("DURATION", "min"),
        duration_max=("DURATION", "max"),
        median_spread_bps=("T_Spread_bps", "median"),
    )
    curve_summary = model_stats.groupby("company_symbol").agg(
        fit_months=("DATE", "nunique"),
        average_bonds=("n_bonds", "mean"),
        median_r2=("r2", "median"),
        median_rmse_bps=("weighted_rmse_bps", "median"),
    )
    excluded = exclusions.iloc[0]
    best_row = combined_returns.loc[combined_returns["portfolio_return"].idxmax()]
    worst_row = combined_returns.loc[combined_returns["portfolio_return"].idxmin()]

    payload = {
        "analysis_date": pd.Timestamp(analysis_date).isoformat(),
        "selected_trial": scope["SELECTED_TRIAL"],
        "sample": records(sample_summary),
        "curves": records(curve_summary),
        "clean_trials": records(trial_summary),
        "raw_trials": records(raw_trial_summary),
        "combined": records(summary_table.loc[["combined"]])[0],
        "issuers": records(summary_table.drop(index="combined")),
        "costs": records(cost_sensitivity),
        "robustness": records(robustness_table),
        "characteristics": records(characteristics),
        "excluded_mark": {
            "issuer": excluded["company_symbol"],
            "cusip": excluded["CUSIP"],
            "date": pd.Timestamp(excluded["DATE"]).isoformat(),
            "previous_date": pd.Timestamp(excluded["previous_date_qc"]).isoformat(),
            "next_date": pd.Timestamp(excluded["next_date_qc"]).isoformat(),
            "previous_price": float(excluded["previous_price_qc"]),
            "price": float(excluded["PRICE_EOM"]),
            "next_price": float(excluded["next_price_qc"]),
            "yield": float(excluded["YIELD_dec"]),
            "spread_bps": float(excluded["T_Spread_bps"]),
        },
        "observation_counts": {
            "unchecked": int(len(filtered_unchecked)),
            "cleaned": int(len(filtered)),
            "excluded": int(len(exclusions)),
            "valid_next_returns": int(filtered["next_return"].notna().sum()),
        },
        "best_month": {
            "date": pd.Timestamp(best_row["DATE"]).isoformat(),
            "return": float(best_row["portfolio_return"]),
        },
        "worst_month": {
            "date": pd.Timestamp(worst_row["DATE"]).isoformat(),
            "return": float(worst_row["portfolio_return"]),
        },
    }
    (BUILD_DIR / "report_data.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    colors_map = {
        "navy": "#17324D",
        "teal": "#15808D",
        "gold": "#D5A021",
        "red": "#B24A3A",
        "gray": "#6C7882",
    }
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.labelsize": 9,
        "axes.edgecolor": "#AEB8BF",
        "axes.grid": True,
        "grid.color": "#E6EBEE",
        "grid.linewidth": 0.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
    })

    price_path = filtered_unchecked[
        (filtered_unchecked["CUSIP"] == excluded["CUSIP"])
        & (filtered_unchecked["DATE"] >= pd.Timestamp("2024-06-01"))
    ].sort_values("DATE")
    fig, ax = plt.subplots(figsize=(8.4, 2.8))
    ax.plot(price_path["DATE"], price_path["PRICE_EOM"], color=colors_map["navy"], linewidth=2.0, marker="o", markersize=4)
    flag = price_path[price_path["DATE"] == excluded["DATE"]]
    ax.scatter(flag["DATE"], flag["PRICE_EOM"], s=90, color=colors_map["red"], edgecolor="white", linewidth=1.4, zorder=4, label="Excluded month-end mark")
    ax.annotate(f"{excluded['PRICE_EOM']:.2f}", (excluded["DATE"], excluded["PRICE_EOM"]), xytext=(14, 10), textcoords="offset points", color=colors_map["red"], fontweight="bold")
    ax.set_title(f"Price history around the isolated {excluded['CUSIP']} observation")
    ax.set_ylabel("Month-end price")
    ax.set_xlabel("")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.legend(frameon=False, loc="lower left")
    fig.tight_layout()
    savefig(fig, "price_quality.png")

    fig, axes = plt.subplots(2, 3, figsize=(10.2, 5.9))
    for ax, issuer in zip(axes.flat, scope["SELECTED_ISSUERS"]):
        group = plot_df[plot_df["company_symbol"] == issuer].sort_values("DURATION")
        sizes = np.sqrt(group["T_DVolume_num"].fillna(0).clip(lower=0))
        sizes = 18 + 55 * sizes / sizes.max() if sizes.max() > 0 else 30
        ax.scatter(group["DURATION"], group["T_Spread_bps"], s=sizes, color=colors_map["teal"], alpha=0.62, edgecolors="none")
        ax.plot(group["DURATION"], group["spread_fit_bps"], color=colors_map["navy"], linewidth=1.8)
        ax.set_title(f"{issuer} ({len(group)} bonds)", fontweight="bold")
        ax.set_xlabel("Duration")
        ax.set_ylabel("Spread (bps)")
    fig.suptitle(f"Issuer spread curves on {pd.Timestamp(analysis_date):%B %d, %Y}", fontsize=13, fontweight="bold", color=colors_map["navy"])
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    savefig(fig, "issuer_curves.png")

    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    pass_colors = [colors_map["gray"], colors_map["teal"], colors_map["gold"]]
    for (name, (_, _, monthly)), color in zip(trial_outputs.items(), pass_colors):
        cumulative = (1 + monthly.set_index("DATE")["portfolio_return"]).cumprod() - 1
        ax.plot(cumulative.index, cumulative, linewidth=2.0, label=name.split(" - ")[0], color=color)
    ax.axhline(0, color="#303840", linewidth=0.8)
    ax.set_title("Cumulative gross return across the three portfolio specifications")
    ax.set_ylabel("Cumulative return")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.legend(frameon=False, ncol=3, loc="upper left")
    fig.tight_layout()
    savefig(fig, "main_cumulative.png")

    fig, ax = plt.subplots(figsize=(8.4, 3.0))
    cost_labels = [str(index) for index in cost_sensitivity.index]
    cost_values = cost_sensitivity["annualized_return"].to_numpy()
    bars = ax.bar(cost_labels, cost_values, color=[colors_map["teal"], colors_map["gold"], colors_map["red"], colors_map["navy"]], alpha=0.88)
    ax.axhline(0, color="#303840", linewidth=0.9)
    ax.set_title("Pass 2 annualized return after one-way turnover costs")
    ax.set_ylabel("Annualized return")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    for bar in bars:
        value = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, value + (0.001 if value >= 0 else -0.001), f"{value:.2%}", ha="center", va="bottom" if value >= 0 else "top", fontsize=8, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "cost_sensitivity.png")

    labels = ["Pass 1\nBaseline", "Pass 2\nConcentrated", "Pass 3\nLiquidity-aware"]
    untouched_values = raw_trial_summary["gross_annualized_return"].to_numpy()
    main_values = trial_summary["gross_annualized_return"].to_numpy()
    x_values = np.arange(len(labels))
    bar_width = 0.34
    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    untouched_bars = ax.bar(x_values - bar_width / 2, untouched_values, bar_width, color=colors_map["gray"], label="Untouched data")
    main_bars = ax.bar(x_values + bar_width / 2, main_values, bar_width, color=colors_map["teal"], label="Main sample")
    ax.axhline(0, color="#303840", linewidth=0.8)
    ax.set_xticks(x_values, labels)
    ax.set_ylabel("Gross annualized return")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Data-quality sensitivity of the annualized return")
    ax.legend(frameon=False, loc="upper left")
    for bars in (untouched_bars, main_bars):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.0015, f"{bar.get_height():.2%}", ha="center", va="bottom", fontsize=8, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "data_sensitivity.png")

    print(f"Wrote report data and charts to {BUILD_DIR}")


if __name__ == "__main__":
    main()
