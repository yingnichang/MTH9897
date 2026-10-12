"""The tracked result contract: aggregate-only results, the hash-checking loader, and run_all's --only flag."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

FINAL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FINAL))
from research import results, run_all  # noqa: E402
from research.studies._common import Context  # noqa: E402


def test_results_are_aggregate_only(tmp_path):
    # Every tracked results CSV passes the check.
    files = sorted((FINAL / "results").rglob("*.csv"))
    for f in files:
        results.check_aggregate(pd.read_csv(f), f)
    # The check itself rejects security identifiers and security-month rows.
    with pytest.raises(ValueError, match="security-level"):
        results.check_aggregate(pd.DataFrame({"date": ["2000-01-31"], "PERMNO": [1], "x": [0.1]}), "f.csv")
    with pytest.raises(ValueError, match="security-level"):
        results.check_aggregate(pd.DataFrame({"comnam": ["ACME"], "x": [0.1]}), "f.csv")
    with pytest.raises(ValueError, match="security-level"):
        results.check_aggregate(pd.DataFrame({"Ticker ": ["AC"]}), "f.csv")
    results.check_aggregate(pd.DataFrame({"date": ["2000-01-31"], "names": [100], "permno_count": [3]}), "f.csv")


def write_study(root, study, name, df, meta=None):
    d = root / study
    d.mkdir(parents=True, exist_ok=True)
    df.to_csv(d / name, index=False)
    return results.file_record(root, study, name, meta or {"description": "x", "window": "w", "returns": "gross",
                                                         "role": "primary"})


def test_loader_rejects_hash_mismatch(tmp_path):
    rec = write_study(tmp_path, "s", "a.csv", pd.DataFrame({"x": [0.1, 0.2]}))
    (tmp_path / "manifest.json").write_text(json.dumps({"files": {"s/a.csv": rec}}), encoding="utf-8")
    df, meta = results.load("s", "a.csv", root=tmp_path)
    assert df["x"].tolist() == [0.1, 0.2] and meta["role"] == "primary" and meta["sha256"] == rec["sha256"]
    (tmp_path / "s" / "a.csv").write_text("x\n0.1\n0.3\n", encoding="utf-8")
    with pytest.raises(results.ResultHashError):
        results.load("s", "a.csv", root=tmp_path)
    with pytest.raises(KeyError):
        results.load("s", "missing.csv", root=tmp_path)


def test_run_all_only_flag(tmp_path):
    calls = []

    def make(name, value):
        class Study:
            NAME = name
            FILES = {"t.csv": {"description": f"{name} table", "window": "2000", "returns": "gross", "role": "primary"}}
            DEPENDS = ()

            @staticmethod
            def run(ctx):
                calls.append(name)
                pd.DataFrame({"date": ["2000-01-31"], "v": [value]}).to_csv(ctx.out(name) / "t.csv", index=False)
        return Study

    reg = {"a": make("a", 1.0), "b": make("b", 2.0)}
    run_all.main(["--results", str(tmp_path / "r"), "--output", str(tmp_path / "o")], registry=reg)
    assert calls == ["a", "b"]
    m1 = json.loads((tmp_path / "r" / "manifest.json").read_text(encoding="utf-8"))
    assert set(m1["files"]) == {"a/t.csv", "b/t.csv"} and set(m1["studies"]) == {"a", "b"}
    reg["b"] = make("b", 3.0)
    run_all.main(["--only", "b", "--results", str(tmp_path / "r"), "--output", str(tmp_path / "o")], registry=reg)
    assert calls == ["a", "b", "b"]
    m2 = json.loads((tmp_path / "r" / "manifest.json").read_text(encoding="utf-8"))
    assert m2["files"]["a/t.csv"] == m1["files"]["a/t.csv"]              # untouched study kept as it was
    assert m2["files"]["b/t.csv"]["sha256"] != m1["files"]["b/t.csv"]["sha256"]
    assert results.load("b", "t.csv", root=tmp_path / "r")[0]["v"].iloc[0] == 3.0
    with pytest.raises(SystemExit):
        run_all.main(["--only", "zzz", "--results", str(tmp_path / "r")], registry=reg)
    # A non-default --end may not write into the primary results directory.
    with pytest.raises(SystemExit):
        run_all.main(["--end", "2016-12-31"], registry=reg)
    # A study writing an undeclared file, or missing a declared one, fails the run.
    class Bad:
        NAME, FILES, DEPENDS = "c", {"t.csv": {"description": "", "window": "", "returns": "", "role": "primary"}}, ()

        @staticmethod
        def run(ctx):
            pd.DataFrame({"v": [1]}).to_csv(ctx.out("c") / "other.csv", index=False)
    with pytest.raises(ValueError, match="declared"):
        run_all.main(["--only", "c", "--results", str(tmp_path / "r")], registry={"c": Bad})


# --- Provenance across partial runs: a -> b -> c, each reading its dependency through ctx.result. ---

def chain(calls, values, fixed_end=None):
    def make(name, depends):
        class Study:
            NAME, DEPENDS = name, depends
            FILES = {"t.csv": {"description": f"{name} table", "window": "2000", "returns": "gross", "role": "primary"}}
            FIXED_END = fixed_end

            @staticmethod
            def run(ctx):
                calls.append(name)
                base = sum(pd.read_csv(ctx.result(d, "t.csv"))["v"].iloc[0] for d in depends)
                pd.DataFrame({"date": ["2000-01-31"], "v": [base + values[name]]}).to_csv(ctx.out(name) / "t.csv",
                                                                                         index=False)
        return Study
    return {"a": make("a", ()), "b": make("b", ("a",)), "c": make("c", ("b",))}


@pytest.fixture
def provenance(monkeypatch):
    """Current data-manifest hash and per-study source hashes, controlled by the test."""
    state = {"data": "data-1", "src": {"a": "a-1", "b": "b-1", "c": "c-1"}}
    monkeypatch.setattr(run_all, "data_hash", lambda: state["data"])
    monkeypatch.setattr(run_all, "study_sources", lambda study: {f"{study.NAME}.py": state["src"][study.NAME]})
    return state


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_partial_run_rejects_stale_dependency_provenance(tmp_path, provenance):
    calls, values = [], {"a": 1.0, "b": 10.0, "c": 100.0}
    reg, root = chain(calls, values), tmp_path / "r"
    args = ["--results", str(root), "--output", str(tmp_path / "o")]
    man = run_all.main(args, registry=reg)
    assert calls == ["a", "b", "c"]
    pa, pb = man["studies"]["a"]["provenance"], man["studies"]["b"]["provenance"]
    assert pa["data_manifest_sha256"] == "data-1" and pa["sources"] == {"a.py": "a-1"}
    assert pb["inputs"] == {"a/t.csv": man["files"]["a/t.csv"]["sha256"]}
    assert set(pb["depends"]) == {"a"}
    before = snapshot(root)
    # Changed data, or a changed source of the dependency: --only b is refused and nothing is written.
    for change in ({"data": "data-2"}, {"src": {"a": "a-2", "b": "b-1", "c": "c-1"}}):
        saved = {k: provenance[k] for k in change}
        provenance.update(change)
        with pytest.raises(SystemExit):
            run_all.main(["--only", "b", *args], registry=reg)
        assert calls == ["a", "b", "c"] and snapshot(root) == before
        provenance.update(saved)
    # Current provenance: the partial run proceeds.
    run_all.main(["--only", "b", *args], registry=reg)
    assert calls[-1] == "b"
    # A manifest without per-study provenance (the old format) is not trusted either.
    text = (root / "manifest.json").read_text(encoding="utf-8")
    m = json.loads(text)
    del m["studies"]["a"]["provenance"]
    (root / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(SystemExit):
        run_all.main(["--only", "b", *args], registry=reg)
    (root / "manifest.json").write_text(text, encoding="utf-8")
    # Rerunning a alone leaves b's recorded input stale, so a later --only c is refused.
    values["a"] = 2.0
    run_all.main(["--only", "a", *args], registry=reg)
    n = len(calls)
    with pytest.raises(SystemExit):
        run_all.main(["--only", "c", *args], registry=reg)
    assert len(calls) == n


def test_context_result_rejects_modified_dependency(tmp_path, provenance):
    calls, reg, root = [], chain([], {"a": 1.0, "b": 10.0, "c": 100.0}), tmp_path / "r"
    args = ["--results", str(root), "--output", str(tmp_path / "o")]
    run_all.main(args, registry=reg)
    (root / "a" / "t.csv").write_text("date,v\n2000-01-31,999\n", encoding="utf-8")
    with pytest.raises(results.ResultHashError):
        Context(results=root).result("a", "t.csv")
    with pytest.raises(results.ResultHashError):
        results.load("a", "t.csv", root=root)
    with pytest.raises(SystemExit):                                  # the stale dependency is caught before b runs
        run_all.main(["--only", "b", *args], registry=reg)
    (root / "a" / "x.csv").write_text("v\n1\n", encoding="utf-8")   # present on disk but not in the manifest
    with pytest.raises(results.ResultHashError):
        Context(results=root).result("a", "x.csv")
    with pytest.raises(FileNotFoundError):
        Context(results=root).result("a", "missing.csv")


def test_with_deps_recomputes(tmp_path, provenance):
    calls, values = [], {"a": 1.0, "b": 10.0, "c": 100.0}
    reg, root = chain(calls, values), tmp_path / "r"
    args = ["--results", str(root), "--output", str(tmp_path / "o")]
    run_all.main(args, registry=reg)
    # Nothing stale: --with-deps reruns only the selected study.
    run_all.main(["--only", "c", "--with-deps", *args], registry=reg)
    assert calls == ["a", "b", "c", "c"]
    # a's source changes: a, and b (which read a), are recomputed before c.
    provenance["src"]["a"], values["a"] = "a-2", 5.0
    man = run_all.main(["--only", "c", "--with-deps", *args], registry=reg)
    assert calls[4:] == ["a", "b", "c"]
    assert man["studies"]["a"]["provenance"]["sources"] == {"a.py": "a-2"}
    assert results.load("c", "t.csv", root=root)[0]["v"].iloc[0] == 115.0
    assert man["studies"]["c"]["provenance"]["depends"]["b"] == run_all.fingerprint(man, "b")
    run_all.main(["--only", "c", *args], registry=reg)               # now consistent without --with-deps
    assert calls[-1] == "c"
    # A dependency absent from the results directory is computed with --with-deps.
    calls.clear()
    run_all.main(["--only", "b", "--with-deps", "--results", str(tmp_path / "r2")], registry=reg)
    assert calls == ["a", "b"]


def test_fixed_end_rejected_before_writing(tmp_path, provenance):
    reg = chain([], {"a": 1.0, "b": 10.0, "c": 100.0}, fixed_end=pd.Timestamp("2024-12-31"))
    root = tmp_path / "new"
    with pytest.raises(SystemExit):
        run_all.main(["--end", "2016-12-31", "--results", str(root), "--output", str(tmp_path / "o")], registry=reg)
    assert not root.exists()


def test_documented_rehearsal_is_supported():
    """The shortened rehearsal in README.md and in run_all's docstring selects a dependency-closed set of studies
    that accept a non-default --end."""
    from research.studies import REGISTRY
    lines = [ln for ln in [*(FINAL / "README.md").read_text(encoding="utf-8").splitlines(),
                           *run_all.__doc__.splitlines()] if "results_rehearsal" in ln]
    assert len(lines) == 2
    for ln in lines:
        argv = ln.split("#")[0].split()[3:]
        only = argv[argv.index("--only") + 1:argv.index("--end")]
        assert argv[argv.index("--end") + 1] == "2016-12-31" and only
        for s in only:
            assert getattr(REGISTRY[s], "FIXED_END", None) is None, s
            assert set(REGISTRY[s].DEPENDS) <= set(only), s
