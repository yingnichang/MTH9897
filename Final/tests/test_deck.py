"""The slide deck builds from results/ with titled slides, speaker notes and no security-level identifiers."""
import sys
from pathlib import Path

import pytest

FINAL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FINAL))
sys.path.insert(0, str(FINAL / "presentation"))
pptx = pytest.importorskip("pptx")
import build_deck  # noqa: E402


@pytest.mark.skipif(not (FINAL / "results" / "manifest.json").exists(), reason="results/ not generated")
def test_deck_builds_with_titled_slides(tmp_path):
    path = build_deck.build(out_dir=tmp_path)
    prs = pptx.Presentation(str(path))
    assert 12 <= len(prs.slides) <= 15
    for i, slide in enumerate(prs.slides, 1):
        texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
        assert texts and texts[0].strip(), f"slide {i} has no title"
        assert slide.notes_slide.notes_text_frame.text.strip(), f"slide {i} has no speaker notes"
    notes = (tmp_path / "speaker_notes.md").read_text(encoding="utf-8")
    assert notes.count("\n## ") == len(prs.slides)
    headers = [c.text for s in prs.slides for sh in s.shapes if sh.has_table for c in list(sh.table.rows)[0].cells]
    assert headers and not build_deck.results.security_headers(headers)


@pytest.mark.skipif(not (FINAL / "results" / "manifest.json").exists(), reason="results/ not generated")
def test_deck_states_optimizer_inference_from_results(tmp_path):
    """The optimizer slide asserts the inference that the CSV supports: the count of 95% intervals that exclude zero."""
    from research import summary as S
    g = build_deck.results.load("optimization", "grid_subperiods.csv")[0]
    w = g.loc[g.role.eq("spec") & g.c0_bps.eq(30) & g.period.eq("1990–2024") & g.delta.isin(["2%", "5%"])
              & g.tau.isin(["20%", "40%"])]
    excl = int(((w.carhart_alpha_ci95_low > 0) | (w.carhart_alpha_ci95_high < 0)).sum())
    N = S.numbers()
    assert N["opt_ci_9024_excl"] == excl and N["opt_ci_9024_text"] == S.intervals_vs_zero(
        w.carhart_alpha_ci95_low, w.carhart_alpha_ci95_high)
    prs = pptx.Presentation(str(build_deck.build(out_dir=tmp_path)))
    text = "\n".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame)
    notes = (tmp_path / "speaker_notes.md").read_text(encoding="utf-8")
    assert N["opt_ci_9024_text"] in text and "unadjusted" in text.lower()
    assert "touch zero" not in text + notes and "touching zero" not in text + notes
