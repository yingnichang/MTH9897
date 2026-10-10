"""Paths and research conventions shared by every pipeline stage."""
from pathlib import Path

FINAL = Path(__file__).resolve().parent.parent
DATA = FINAL / "data"
RAW = DATA / "raw"
AUDIT = DATA / "audit"

PANEL_FILE = DATA / "crsp_monthly_normalized.parquet"
BENCHMARK_FILE = DATA / "benchmark_monthly.csv"
FACTORS_FILE = DATA / "ff_factors_monthly.csv"
MANIFEST_FILE = DATA / "manifest.json"

# Sample. CRSP monthly prices begin 1925-12-31, so the first full 36-month return window ends
# December 1928, which is the first formation date for a January 1929 investment start.
EXTRACT_START = "1925-12-31"
EXTRACT_END = "2024-12-31"      # legacy (SIZ) CRSP files are frozen at the December 2024 release
BENCHMARK_START = "1926-07-31"  # first month of the Fama-French risk-free series
FIRST_INVESTMENT = "1929-01-31"
PAPER_END = "2016-12-31"

# Point-in-time security screens (CRSP legacy header codes).
COMMON_SHARE_CODES = (10, 11)   # US ordinary common shares
EXCHANGE_CODES = (1, 2, 3)      # NYSE, NYSE American (AMEX), NASDAQ; excludes when-issued codes 31-33

# Missing delisting returns. Performance-related delistings (500, 520-584) with no CRSP delisting
# return receive Shumway (1997) / Shumway and Warther (1999) values; all other missing delisting
# returns are set to zero. Each imputation is flagged in `delist_source` and counted in the audit.
PERFORMANCE_DELIST_CODES = frozenset([500, *range(520, 585)])
DELIST_IMPUTE_NYSE_AMEX = -0.30
DELIST_IMPUTE_NASDAQ = -0.55
DELIST_ACTIVE_CODE = 100

# Implied dividends: ret - retx. Values in [-tol, 0) are numerical noise and set to zero; values
# below -tol are treated as unknown distributions and counted.
DIV_NEGATIVE_TOL = 1e-6

# Missing returns of held stocks (DATA-002, DATA-010). A missing-return month with a CRSP price earns
# the price ratio to the last positive price if that price is at most this many calendar months
# earlier (one holding quarter); otherwise it is carried at the stale price (0).
PRICE_RATIO_MAX_LOOKBACK_MONTHS = 3

UNIVERSE_SIZE = 1000
HISTORY_MONTHS = 36
