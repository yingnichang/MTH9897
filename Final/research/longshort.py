"""Simple long/short construction with overlapping cohorts (Instructions.md Trading 1A-C, 4-6).
Conventions are fixed in experiments/2026-10-11-long-short-construction (before any result).

A separate accounting path: `research.engine` (the paper's long-only engine) is not used or changed.

- Each month-end f a new cohort is formed: long the names in `long`, short the names in `short`, equal
  weight, each leg 1/n of NAV (dollar-neutral at formation). It is traded at the close of f, held in months
  f+1..f+n and unwound at the close of month f+n. The ledger labels a trade with the month whose return its
  cost reduces (f+1 for an open, f+n+1 for an unwind), matching the paper engine's cost timing.
- Positions are fractions of NAV. The collateral (NAV) earns rf. A month's gross return is
  long P&L - short P&L + rf - borrow; net = (1 - c x traded) x (1 + gross) - 1, with c per dollar traded per
  side. After the month every position grows with its return and is divided by (1 + gross), so positions do
  not depend on the cost level (as in the engine's proportional haircut).
- A name with a terminal (exit) month settles at its exit return: its P&L is earned once and the position
  becomes cash, without a trading cost. A held name without a return and without an exit raises.
- Borrow on shorts is charged per month held on the short value, at a rate set at formation.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def borrow_rate(cap_decile: int) -> float:
    """Monthly borrow rate, linear in the universe cap decile at formation: 25 bp (decile 1, smallest) to
    2 bp (decile 10, largest)."""
    return (25 - (cap_decile - 1) * 23 / 9) * 1e-4


@dataclass
class Cohort:
    formation: pd.Timestamp
    long: np.ndarray            # permnos
    short: np.ndarray           # permnos
    short_rate: np.ndarray      # monthly borrow rate per short name


def simulate(cohorts: dict, returns: pd.DataFrame, rf: pd.Series, months: pd.DatetimeIndex, n: int,
             borrow: bool = True, keep_positions: bool = False):
    """Run the overlapping-cohort long/short over `months`.

    Returns (records by month, trade ledger, name-level P&L) and, if keep_positions, a fourth frame of
    start-of-month positions (date, permno, side, value as a fraction of NAV).
    """
    ret = {d: g.set_index("permno") for d, g in returns[["date", "permno", "ret_hold", "is_exit"]].groupby("date")}
    live = []                     # [cohort, age, long_ids, long_val, short_ids, short_val, short_rate]
    records, ledger, pnl_rows, pos_rows = [], [], [], []
    for q in months:
        f_new = q - pd.offsets.MonthEnd(1)
        traded = long_traded = short_traded = 0.0
        # Unwind cohorts that have been held n months (trade at the close of the previous month).
        keep = []
        for c in live:
            if c[1] >= n:
                for ids, vals, side, sign in [(c[2], c[3], "long", -1), (c[4], c[5], "short", 1)]:
                    for pid, v in zip(ids, vals):
                        ledger.append((q, c[0], pid, side, "close", sign * v))
                    t = float(np.abs(vals).sum())
                    traded += t
                    long_traded, short_traded = (long_traded + t, short_traded) if side == "long" else (long_traded, short_traded + t)
            else:
                keep.append(c)
        live = keep
        # Open the cohort formed at the previous month-end.
        if f_new in cohorts:
            co = cohorts[f_new]
            lv = np.full(len(co.long), 1 / n / len(co.long))
            sv = np.full(len(co.short), 1 / n / len(co.short))
            for pid, v in zip(co.long, lv):
                ledger.append((q, f_new, pid, "long", "open", v))
            for pid, v in zip(co.short, sv):
                ledger.append((q, f_new, pid, "short", "open", -v))
            traded += 2 / n
            long_traded += 1 / n
            short_traded += 1 / n
            live.append([f_new, 0, np.array(co.long), lv, np.array(co.short), sv, np.array(co.short_rate, float)])
        if q not in ret:
            raise ValueError(f"No returns for {q.date()}")
        month = ret[q]
        long_pnl = short_pnl = borrow_cost = long_exp = short_exp = 0.0
        for c in live:
            long_exp += c[3].sum()
            short_exp += c[5].sum()
            if keep_positions:
                pos_rows += [(q, pid, "long", v) for pid, v in zip(c[2], c[3])]
                pos_rows += [(q, pid, "short", v) for pid, v in zip(c[4], c[5])]
            for leg in ("long", "short"):
                ids, vals = (c[2], c[3]) if leg == "long" else (c[4], c[5])
                rows = month.reindex(ids)
                bad = rows["ret_hold"].isna().to_numpy()
                if bad.any():
                    raise ValueError(f"Missing return at {q.date()} for held {leg} names {ids[bad][:5].tolist()}")
                r = rows["ret_hold"].to_numpy(float)
                p = vals * r
                if leg == "long":
                    long_pnl += p.sum()
                else:
                    short_pnl += p.sum()
                    if borrow:
                        borrow_cost += float((vals * c[6]).sum())
                pnl_rows += [(q, c[0], pid, leg, pv if leg == "long" else -pv) for pid, pv in zip(ids, p)]
                grown = vals * (1 + r)
                exited = rows["is_exit"].astype(bool).to_numpy()
                for pid, v in zip(ids[exited], grown[exited]):
                    ledger.append((q, c[0], pid, leg, "exit", (-v if leg == "long" else v)))
                if leg == "long":
                    c[2], c[3] = ids[~exited], grown[~exited]
                else:
                    c[4], c[5], c[6] = ids[~exited], grown[~exited], c[6][~exited]
        gross = long_pnl - short_pnl + float(rf.loc[q]) - borrow_cost
        for c in live:
            c[3] = c[3] / (1 + gross)
            c[5] = c[5] / (1 + gross)
            c[1] += 1
        records.append({"date": q, "gross": gross, "traded": traded, "long_traded": long_traded,
                        "short_traded": short_traded, "long_pnl": long_pnl, "short_pnl": short_pnl,
                        "borrow": borrow_cost, "rf": float(rf.loc[q]), "long_exposure": long_exp,
                        "short_exposure": short_exp, "live_cohorts": len(live)})
    rec = pd.DataFrame(records).set_index("date")
    led = pd.DataFrame(ledger, columns=["date", "cohort", "permno", "side", "action", "notional"])
    led["cost_10bps"] = np.where(led["action"].eq("exit"), 0.0, 10e-4 * led["notional"].abs())
    pnl = pd.DataFrame(pnl_rows, columns=["date", "cohort", "permno", "side", "pnl"])
    if keep_positions:
        return rec, led, pnl, pd.DataFrame(pos_rows, columns=["date", "permno", "side", "value"])
    return rec, led, pnl


def net_return(rec: pd.DataFrame, bps: float) -> pd.Series:
    """Net return at `bps` per dollar traded per side: (1 - c x traded) x (1 + gross) - 1."""
    return (1 - bps * 1e-4 * rec["traded"]) * (1 + rec["gross"]) - 1


def contributions(rec: pd.DataFrame, bps: float) -> pd.DataFrame:
    """Additive monthly split of the net return: long leg net of rf on its exposure and its own trading cost;
    short leg (rf earned on the short proceeds minus the short P&L) net of its trading cost and borrow; and
    rf on the remaining collateral. They sum to gross - c x traded, the additive approximation of the
    multiplicative net (the difference is reported separately)."""
    c = bps * 1e-4
    out = pd.DataFrame(index=rec.index)
    out["long"] = rec["long_pnl"] - rec["rf"] * rec["long_exposure"] - c * rec["long_traded"]
    out["short"] = rec["rf"] * rec["short_exposure"] - rec["short_pnl"] - c * rec["short_traded"] - rec["borrow"]
    out["collateral_rf"] = rec["rf"] * (1 - rec["long_exposure"] + rec["short_exposure"])
    out["additive_total"] = out.sum(axis=1)
    out["net"] = net_return(rec, bps)
    return out
