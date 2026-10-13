"""Regression coverage for issues found in the three-pass final review."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pytest
from research import cache, mean_variance as mv, optimize as opt, results
from research.studies._common import Context
from crsp_pipeline.signals import build_signals


def test_cache_rejects_modified_and_foreign_bytes(tmp_path, monkeypatch):
    producer = {"data": "current", "sources": "current"}
    monkeypatch.setattr(cache, "identity", lambda ctx: producer)
    ctx = Context(output=tmp_path, study_records={})
    path = tmp_path/"diagnostics_universe.parquet"
    path.write_bytes(b"original cache")
    rec = cache.record_universe(ctx, path)
    ctx.study_records = {"diagnostics": {"provenance": {"caches_produced": {cache.KEY: rec}}}}
    assert ctx.universe_cache() == path and ctx.cache_reads[cache.KEY] == rec
    path.write_bytes(b"modified cache")
    with pytest.raises(results.ResultHashError, match="modified"):
        ctx.universe_cache()
    path.write_bytes(b"original cache")
    foreign = {**rec, "producer": {"data": "foreign"}}
    path.with_suffix(".metadata.json").write_text(json.dumps(foreign), encoding="utf-8")
    with pytest.raises(results.ResultHashError, match="another run"):
        ctx.universe_cache()


def test_alternate_output_rebuilds_only_identical_producer(tmp_path, monkeypatch):
    from research.studies import diagnostics
    monkeypatch.setattr(cache, "identity", lambda ctx: {"source": "current"})
    original = Context(output=tmp_path/"original")
    original.output.mkdir()
    p = original.output/"diagnostics_universe.parquet"
    p.write_bytes(b"reproducible")
    rec = cache.record_universe(original, p)
    alternate = Context(output=tmp_path/"alternate", study_records={"diagnostics": {
        "provenance": {"caches_produced": {cache.KEY: rec}}}})
    def rebuild(ctx):
        ctx.output.mkdir()
        p = ctx.output/"diagnostics_universe.parquet"
        p.write_bytes(b"reproducible")
        cache.record_universe(ctx, p)
    monkeypatch.setattr(diagnostics, "build_universe", rebuild)
    assert alternate.universe_cache().read_bytes() == b"reproducible"
    assert alternate.cache_reads == {cache.KEY: rec}


def test_payout_repurchases_issuance_and_split():
    dates = pd.date_range("2000-01-31", periods=40, freq="ME")
    def frame(latest, split=False):
        shares = np.full(40, 100.0)
        shares[-1] = latest
        raw_shares = shares.copy()
        factor = np.ones(40)
        if split:
            raw_shares[:-1] /= 4
            factor[:-1] *= 4
        return pd.DataFrame({"date": dates, "permno": 1, "ret_total": 0.01, "ret_price": 0.01,
                             "div_cash_adj": 0.1, "price_adj": 10., "shares_adj": raw_shares*factor})
    unchanged = build_signals(frame(100)).iloc[-1]
    repurchase = build_signals(frame(80)).iloc[-1]
    issuance = build_signals(frame(120)).iloc[-1]
    split = build_signals(frame(100, split=True)).iloc[-1]
    assert unchanged.npy == pytest.approx(.12)
    assert repurchase.npy > unchanged.npy > issuance.npy
    assert split.npy == pytest.approx(unchanged.npy)
    assert repurchase.npy == pytest.approx(.12+1-80/((23*100+80)/24))


def test_qp_uses_covariance_and_obeys_caps_bands():
    n = 100
    names = pd.Index(np.arange(n))
    x = np.linspace(0, 4*np.pi, 36)
    r = pd.DataFrame(np.c_[np.tile((.08*np.sin(x))[:, None], (1, 50)),
                          np.tile((.01*np.cos(x))[:, None], (1, 50))], columns=names)
    groups = pd.Series(["A"]*50+["B"]*50, index=names)
    alpha = pd.Series(0.0, index=names)
    costs = pd.Series(0.0, index=names)
    bounds = opt.industry_bounds(groups, pd.Series(1., index=names), None)
    weights, rec = mv.solve(alpha, r, pd.Series(dtype=float), costs, groups, bounds, None)
    assert weights.sum() == pytest.approx(1)
    assert weights.max() <= .020002
    assert weights.reindex(names[:50], fill_value=0).sum() < .1
    assert rec["max_violation"] < 2e-6
    # This is an actual risk penalty: tighter industry bands force more high-risk assets and increase predicted risk.
    tight = opt.industry_bounds(groups, pd.Series(1., index=names), .05)
    w2, rec2 = mv.solve(alpha, r, pd.Series(dtype=float), costs, groups, tight, None)
    assert .45-2e-6 <= w2.reindex(names[:50], fill_value=0).sum() <= .55+2e-6
    assert rec2["predicted_vol_annual"] > rec["predicted_vol_annual"]
    with pytest.raises(ValueError, match="36 complete"):
        mv.solve(alpha, r.iloc[:-1], pd.Series(dtype=float), costs, groups, tight, None)


def test_ff3_controls_recover_known_historical_loadings():
    from research.fmp import ff3_betas
    rng = np.random.default_rng(9897)
    dates = pd.date_range("2000-01-31", periods=36, freq="ME")
    f = pd.DataFrame(rng.normal(0, .03, (36, 3)), index=dates, columns=["mktrf", "smb", "hml"])
    f["rf"] = .002
    known = np.array([[.8, .2, -.3], [1.2, -.4, .7]])
    r = pd.DataFrame(f[["mktrf", "smb", "hml"]].to_numpy()@known.T+.001+f.rf.to_numpy()[:, None], index=dates)
    beta = ff3_betas(r, f)
    assert np.allclose(beta.to_numpy(), known, atol=1e-12)
    with pytest.raises(ValueError, match="Too few"):
        ff3_betas(r.iloc[:23], f)


def test_qp_objective_matches_independent_dense_optimizer():
    from scipy.optimize import minimize
    rng = np.random.default_rng(21)
    names = pd.Index(np.arange(100))
    r = pd.DataFrame(rng.normal(0, .04, (36, 100)), columns=names)
    alpha = pd.Series(rng.normal(0, .0001, 100), index=names)
    groups = pd.Series("A", index=names)
    bounds = opt.industry_bounds(groups, pd.Series(1., index=names), None)
    w, info = mv.solve(alpha, r, pd.Series(dtype=float), pd.Series(.003, index=names), groups, bounds, None)
    cov = np.cov(r.to_numpy().T, ddof=1)
    sigma = 3*(.5*cov+.5*np.diag(np.diag(cov)))
    a = alpha.to_numpy()
    objective = lambda v: 2.5*v@sigma@v-a@v
    ref = minimize(objective, np.full(100, .01), jac=lambda v: 5*sigma@v-a, method="SLSQP",
                   bounds=[(0, .02)]*100, constraints={"type": "eq", "fun": lambda v: v.sum()-1,
                                                       "jac": lambda v: np.ones(100)},
                   options={"ftol": 1e-12, "maxiter": 2000})
    assert ref.success
    assert abs(objective(w.reindex(names, fill_value=0).to_numpy())-ref.fun) < 1e-8


def test_sector_quotas_follow_professor_example():
    from research.studies.professor_checks import sector_quota_weights
    rng = np.random.default_rng(11)
    u = pd.DataFrame({"permno": np.arange(1000), "ff12": ["Tech"]*150+["Other"]*850,
                      "vol36": rng.uniform(.1, .6, 1000), "momentum": rng.normal(size=1000), "npy": rng.normal(size=1000)})
    w, gap = sector_quota_weights(u)
    assert len(w) == 100 and w.sum() == pytest.approx(1)
    assert sum(w.index < 150) == 15 and gap == pytest.approx(0)


def test_completed_study_checkpoint_survives_later_failure(tmp_path):
    from research import run_all
    class First:
        NAME, DEPENDS = "a", ()
        FILES = {"x.csv": {"description": "fixture", "window": "fixture", "returns": "gross", "role": "check"}}
        @staticmethod
        def run(ctx): pd.DataFrame({"value": [1]}).to_csv(ctx.out("a")/"x.csv", index=False)
    class Broken:
        NAME, DEPENDS, FILES = "b", (), First.FILES
        @staticmethod
        def run(ctx): raise RuntimeError("later study failed")
    root = tmp_path/"results"
    with pytest.raises(RuntimeError, match="later study"):
        run_all.main(["--results", str(root), "--output", str(tmp_path/"out")], registry={"a": First, "b": Broken})
    m = results.manifest(root)
    assert m["last_run"]["completed"] == ["a"]
    assert results.load("a", "x.csv", root=root)[0].value.tolist() == [1]
