"""The tracked report notebook: no licensed security-level rows in any output, and cells in sync with the builder."""
import re
import runpy
import sys
from pathlib import Path

import nbformat

FINAL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FINAL))
from research import results  # noqa: E402

NOTEBOOK = FINAL / "conservative_formula_first_draft.ipynb"
HTML_HEADER = re.compile(r"<th[^>]*>(.*?)</th>", re.IGNORECASE | re.DOTALL)


def output_headers(nb):
    """(cell, header) for every table header in the outputs: HTML <th> cells, the column and index-name lines of
    plain-text DataFrame reprs, and markdown table header rows."""
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        for out in cell.get("outputs", []):
            data = out.get("data", {}) if out.output_type in ("display_data", "execute_result") else {}
            if "text/html" in data:
                for h in HTML_HEADER.findall(data["text/html"]):
                    yield i, re.sub(r"<[^>]+>", "", h)
            elif "text/plain" in data:
                for line in data["text/plain"].splitlines()[:2]:
                    for h in line.split():
                        yield i, h
            if "text/markdown" in data:
                for line in data["text/markdown"].splitlines():
                    if line.startswith("|"):
                        for h in line.strip("|").split("|"):
                            yield i, h
                        break
            if out.output_type == "stream":
                for line in out.get("text", "").splitlines()[:2]:
                    for h in line.split():
                        yield i, h


def test_notebook_has_no_security_rows():
    nb = nbformat.read(NOTEBOOK, as_version=4)
    headers = list(output_headers(nb))
    bad = [(i, h) for i, h in headers if results.security_headers([h])]
    assert not bad, f"security-level identifier columns in notebook outputs (cell, header): {bad[:5]}"
    assert headers, "the executed notebook has no table output"
    assert all(c.cell_type != "code" or ".head(" not in c.source for c in nb.cells)


def test_security_scan_catches_identifier_columns():
    nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("x")])
    nb.cells[0].outputs = [nbformat.v4.new_output("display_data", data={
        "text/html": "<table><tr><th>date</th><th>PERMNO</th></tr><tr><td>2000</td><td>10107</td></tr></table>"})]
    assert any(results.security_headers([h]) for _, h in output_headers(nb))
    nb.cells[0].outputs = [nbformat.v4.new_output("display_data", data={
        "text/html": "<table><tr><th>item</th><th>ours</th></tr><tr><td>Share class</td><td>one class per PERMCO</td></tr></table>"})]
    assert not any(results.security_headers([h]) for _, h in output_headers(nb))   # prose is not a column


def test_notebook_matches_builder(monkeypatch):
    """Code and markdown cells (whitespace-normalized) must match what build_notebook.py generates."""
    captured = {}
    monkeypatch.setattr(nbformat, "write", lambda nb, path, **k: captured.setdefault("nb", nb))
    runpy.run_path(str(FINAL / "build_notebook.py"), run_name="__main__")
    norm = lambda cells: [(c.cell_type, " ".join(c.source.split())) for c in cells]
    built, saved = norm(captured["nb"].cells), norm(nbformat.read(NOTEBOOK, as_version=4).cells)
    assert built == saved, "the notebook differs from build_notebook.py; edit the builder and rebuild"


# --- Reported inferences follow the stored intervals. ---

def test_intervals_vs_zero_wording():
    from research import summary as S
    lo, hi = [0.0012, -0.0010, 0.0001, 0.0016], [0.028, 0.037, 0.028, 0.038]
    assert S.zero_count(lo, hi) == (3, 4)
    assert S.intervals_vs_zero(lo, hi) == "three of the four 95% intervals exclude zero"
    assert S.intervals_vs_zero([-0.03, -0.01], [-0.001, 0.02]) == "one of the two 95% intervals excludes zero"
    assert S.intervals_vs_zero([-0.01, -0.02], [0.01, 0.02]) == "none of the two 95% intervals excludes zero"
    assert S.intervals_vs_zero([0.01, -0.05], [0.02, -0.01]) == "both 95% intervals exclude zero"
    assert S.intervals_vs_zero([0.01] * 3, [0.02] * 3) == "all three 95% intervals exclude zero"
    assert S.significance(-0.0366, -0.0029) == "significantly negative"
    assert S.significance(-0.01, 0.02) == "not significantly different from zero"


def markdown_outputs(nb):
    return "\n".join(o["data"]["text/markdown"] for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", [])
                     if o.output_type in ("display_data", "execute_result") and "text/markdown" in o.get("data", {}))


def test_optimizer_inference_matches_results():
    """The count of optimizer intervals excluding zero is computed independently from the CSV and must be the one the
    executed notebook states; the earlier wording ("touch zero") must be gone."""
    from research import summary as S
    g = results.load("optimization", "grid_subperiods.csv")[0]
    w = g.loc[g.role.eq("spec") & g.c0_bps.eq(30) & g.period.eq("1990–2024") & g.delta.isin(["2%", "5%"])
              & g.tau.isin(["20%", "40%"])]
    assert len(w) == 4
    excl = int(((w.carhart_alpha_ci95_low > 0) | (w.carhart_alpha_ci95_high < 0)).sum())
    N = S.numbers()
    assert (N["opt_ci_9024_excl"], N["opt_ci_9024_n"]) == (excl, 4)
    text = markdown_outputs(nbformat.read(NOTEBOOK, as_version=4))
    assert N["opt_ci_9024_text"] in text and N["opt_ci_1724_text"] in text
    assert "unadjusted" in text and "touch zero" not in text and "touching zero" not in text


def test_critical_estimates_shown_with_intervals():
    from research import summary as S
    from research.summary import ci, num
    nb = nbformat.read(NOTEBOOK, as_version=4)
    headers = {h.strip() for _, h in output_headers(nb)}
    for col in ["compounded [95% CI]", "volatility [95% CI]", "Sharpe (paper) [95% CI]", "Sharpe (excess) [95% CI]",
                "excess [95% CI]", "Carhart alpha (NW t) [95% CI]", "FF5+UMD alpha (NW t) [95% CI]"]:
        assert col in headers, col
    N, h = S.numbers(), "1990–2024|net30"
    text = markdown_outputs(nb)
    assert ci(N["ct_ff5_alpha_lo|" + h], N["ct_ff5_alpha_hi|" + h], 2) in text
    assert ci(N["ct_comp_lo|1990–2024|gross"], N["ct_comp_hi|1990–2024|gross"]) in text
    assert ci(N["ct_vol_lo|1990–2024|gross"], N["ct_vol_hi|1990–2024|gross"]) in text
    assert "path statistic" in text or any("path statistic" in c.source for c in nb.cells if c.cell_type == "markdown")


def test_composite_defined_as_mean():
    nb = nbformat.read(NOTEBOOK, as_version=4)
    prose = " ".join(" ".join(c.source.split()) for c in nb.cells if c.cell_type == "markdown")
    assert "composite is the equal-weight mean of the three" in prose
    assert "composite is the sum" not in prose
