"""SIC code -> Fama-French 12 industry, following Kenneth French's `Siccodes12` definitions.

Codes outside every listed range map to "Other"; a missing or zero SIC maps to "Unknown" so that
absent classifications are counted separately instead of being merged into "Other".
"""
import numpy as np
import pandas as pd

FF12_RANGES = {
    "NoDur": [(100, 999), (2000, 2399), (2700, 2749), (2770, 2799), (3100, 3199), (3940, 3989)],
    "Durbl": [(2500, 2519), (2590, 2599), (3630, 3659), (3710, 3711), (3714, 3714), (3716, 3716),
              (3750, 3751), (3792, 3792), (3900, 3939), (3990, 3999)],
    "Manuf": [(2520, 2589), (2600, 2699), (2750, 2769), (3000, 3099), (3200, 3569), (3580, 3629),
              (3700, 3709), (3712, 3713), (3715, 3715), (3717, 3749), (3752, 3791), (3793, 3799),
              (3830, 3839), (3860, 3899)],
    "Enrgy": [(1200, 1399), (2900, 2999)],
    "Chems": [(2800, 2829), (2840, 2899)],
    "BusEq": [(3570, 3579), (3660, 3692), (3694, 3699), (3810, 3829), (7370, 7379)],
    "Telcm": [(4800, 4899)],
    "Utils": [(4900, 4949)],
    "Shops": [(5000, 5999), (7200, 7299), (7600, 7699)],
    "Hlth": [(2830, 2839), (3693, 3693), (3840, 3859), (8000, 8099)],
    "Money": [(6000, 6999)],
}
FF12_NAMES = [*FF12_RANGES, "Other"]


def ff12(sic) -> pd.Series:
    sic = pd.to_numeric(pd.Series(sic), errors="coerce")
    out = pd.Series("Other", index=sic.index, dtype=object)
    for name, ranges in FF12_RANGES.items():
        for lo, hi in ranges:
            out[sic.between(lo, hi)] = name
    out[sic.isna() | sic.le(0)] = "Unknown"
    return out.astype(str)


assert list(ff12([2834, 7372, 6020, 4911, 1311, 0, np.nan, 9999])) == [
    "Hlth", "BusEq", "Money", "Utils", "Enrgy", "Unknown", "Unknown", "Other"]
