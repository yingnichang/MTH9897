"""PDF presentation evidence agrees with saved results. Yingni Chang and Yikai Shen."""
import sys
from pathlib import Path
import pytest
from pypdf import PdfReader
FINAL=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(FINAL));sys.path.insert(0,str(FINAL/'presentation'))
import build_deck


@pytest.mark.skipif(not (FINAL/'results/manifest.json').exists(),reason='results not generated')
def test_deck_builds_with_aligned_scripts(tmp_path):
    pdf=PdfReader(build_deck.build(out_dir=tmp_path))
    from speech_notes import make_notes
    notes=make_notes()
    assert len(pdf.pages)==len(notes)==23
    for page,note in zip(pdf.pages,notes):
        text=page.extract_text()
        assert 'Yingni Chang and Yikai Shen' in text
        assert note['title'].replace('–','-').replace('—','-') in text.replace('–','-').replace('—','-')
    markdown=(tmp_path/'speaker_notes.md').read_text(encoding='utf-8')
    assert markdown.count('\n## ')==23
    text=pdf.pages[17].extract_text()
    from research.feedback_summary import cost_rows,load
    for row in cost_rows(load())[1:]:
        for value in row[1:]:assert value in text


@pytest.mark.skipif(not (FINAL/'results/manifest.json').exists(),reason='results not generated')
def test_optimizer_inference_and_uk_qualifications(tmp_path):
    from research import summary as S
    from numeric_views import make_views
    g=build_deck.results.load('optimization','grid_subperiods.csv')[0]
    w=g.loc[g.role.eq('spec')&g.c0_bps.eq(30)&g.period.eq('1990–2024')&g.delta.isin(['2%','5%'])&g.tau.isin(['20%','40%'])]
    excl=int(((w.carhart_alpha_ci95_low>0)|(w.carhart_alpha_ci95_high<0)).sum())
    n=S.numbers();assert n['opt_ci_9024_excl']==excl
    v=make_views()[14]
    assert [row for row in v['rows'] if row[0]=='95% intervals excluding zero'][0][1]==f"{excl} / {len(w)}"
    pdf=PdfReader(build_deck.build(out_dir=tmp_path))
    text='\n'.join(p.extract_text() for p in pdf.pages[-3:])
    assert 'local currencies' in text.lower() or 'figures are GBP' in text
    assert 'terminal payments' in text and '0.5%' in text
