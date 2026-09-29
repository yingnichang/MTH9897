"""Small regression checks for the submission's data and financial conventions."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

HW2 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HW2 / "src"))

from ff_audit import require_audit, snapshot_audit
from ff_data import FILES, load_all, verify_cache, zipped_csv_text
from sim_cache import CacheMismatch, run_cached
from table1_sim import exact_moments, run_grid, simulate_wealth
from table4_strategies import SelectionError, held_returns, momentum_selections


class PinnedDataTests(unittest.TestCase):
    def test_manifest_describes_committed_bytes_and_release(self):
        manifest = json.loads((HW2 / "data/vintage.json").read_text(encoding="utf-8"))
        paths = verify_cache()
        self.assertEqual(set(paths), set(FILES))
        for key, path in paths.items():
            with self.subTest(file=key):
                content = path.read_bytes()
                entry = manifest[key]
                self.assertEqual(entry["sha256"], hashlib.sha256(content).hexdigest())
                self.assertEqual(entry["bytes"], len(content))
                self.assertEqual(entry["file"], path.name)
                self.assertEqual(entry["header"], zipped_csv_text(content).splitlines()[0])
                self.assertEqual(entry["crsp_vintage"], "202608")
                self.assertTrue(entry["url"].endswith("/" + path.name))

    def test_pinned_data_satisfy_all_snapshot_facts(self):
        paths = verify_cache()
        industries, factors = load_all(paths)
        audit = require_audit(snapshot_audit(paths, industries, factors))
        self.assertEqual(len(audit), 24)
        self.assertEqual(str(factors.index[0]), "1926-07")
        self.assertEqual(str(factors.index[-1]), "2026-08")
        self.assertEqual(len(factors), 1202)

    def test_modified_archive_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for filename in FILES.values():
                shutil.copyfile(HW2 / "data/raw" / filename, target / filename)
            changed = target / FILES["ff49"]
            changed.write_bytes(changed.read_bytes() + b"corruption")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verify_cache(target, HW2 / "data/vintage.json")


class MomentumTimingTests(unittest.TestCase):
    def setUp(self):
        self.index = pd.period_range("2000-01", periods=7, freq="M")
        self.returns = pd.DataFrame(
            {"A": [.10, .10, -.05, -.30, .40, .10, .10],
             "B": [.02, .02, .02, .02, .02, .02, .02]}, index=self.index)
        self.eligible = pd.DataFrame(True, index=self.index, columns=self.returns.columns)

    def test_holding_month_and_future_returns_do_not_change_today_selection(self):
        april = self.index[3]
        baseline = momentum_selections(self.returns, self.eligible, april)
        self.assertEqual(baseline.loc[april], 0)  # 1.10 * 1.10 * .95 > 1.02**3.
        changed = self.returns.copy()
        changed.loc[april:, "A"] = -.99
        changed.loc[april:, "B"] = 9.0
        selected = momentum_selections(changed, self.eligible, april)
        self.assertEqual(selected.loc[april], baseline.loc[april])

    def test_incomplete_lookback_delays_entry(self):
        data = self.returns.copy()
        data.loc[self.index[0], "A"] = np.nan
        data.loc[self.index[1]:self.index[3], "A"] = .20
        positions = momentum_selections(data, self.eligible, self.index[3])
        self.assertEqual(positions.loc[self.index[3]], 1)
        self.assertEqual(positions.loc[self.index[4]], 0)

    def test_selected_missing_return_stops_instead_of_reselecting(self):
        april = self.index[3]
        positions = momentum_selections(self.returns, self.eligible, april)
        data = self.returns.copy()
        data.loc[april, "A"] = np.nan
        with self.assertRaisesRegex(SelectionError, "no holding-month return"):
            held_returns(data, self.eligible, positions)


class SimulationTests(unittest.TestCase):
    def test_single_period_exact_moments_match_normal_distribution(self):
        mean, sd, skew, kurtosis = exact_moments(.000025, .0045, 1)
        np.testing.assert_allclose([mean, sd, skew, kurtosis], [.000025, .0045, 0, 3],
                                   rtol=1e-7, atol=1e-10)

    def test_daily_percent_units_and_trading_year_horizons(self):
        table = run_grid(.0025 / 100, [0.0], 3, 2520,
                         block_lengths=(252, 1260, 2520), periods_per_year=252)
        np.testing.assert_array_equal(table["horizon_years"], [1, 5, 10])
        expected = np.power(1 + .0025 / 100, np.array([252, 1260, 2520])) - 1
        np.testing.assert_allclose(table["mean"], expected, rtol=1e-10)
        np.testing.assert_allclose(table["median"], expected, rtol=1e-10)

    def test_monthly_extension_uses_180_and_240_months(self):
        table = run_grid(.005, [0.0], 3, 240, prefix_lengths=(180, 240))
        np.testing.assert_array_equal(table["horizon_years"], [15, 20])
        np.testing.assert_allclose(table["mean"], [1.005**180 - 1, 1.005**240 - 1], rtol=1e-12)
        for volatility in (.02, .10, .20):
            self.assertAlmostEqual(exact_moments(.005, volatility, 240)[0], 1.005**240 - 1)

    def test_chunk_size_preserves_draws_and_compounding(self):
        settings = dict(mu=.005, sigma=.20, n_paths=37, n_periods=12,
                        block_lengths=(3, 12), prefix_lengths=(5, 12), seed=19)
        small, small_below = simulate_wealth(**settings, chunk_elements=12)
        large, large_below = simulate_wealth(**settings, chunk_elements=10000)
        self.assertEqual(small_below, large_below)
        draws = np.random.default_rng(19).standard_normal((37, 12)) * .20 + 1.005
        for horizon in small:
            np.testing.assert_array_equal(small[horizon], large[horizon])
        np.testing.assert_allclose(small["block", 3], draws.reshape(37, 4, 3).prod(axis=2).ravel())
        np.testing.assert_allclose(small["prefix", 5], draws[:, :5].prod(axis=1))

    def test_modified_simulation_cache_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "simulation.csv"
            run = dict(seeds=[0], mu=.005, sigmas=[.02], n_paths=20,
                       n_periods=12, block_lengths=(12,))
            run_cached(path, **run)
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(CacheMismatch, "changed since it was written"):
                run_cached(path, **run)


if __name__ == "__main__":
    unittest.main()
