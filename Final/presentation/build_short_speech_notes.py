"""Create a brief speaking script for each slide.

Project authors: Yingni Chang and Yikai Shen.
Run from Final: python presentation/build_short_speech_notes.py
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

FINAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FINAL))
from build_report_pdf import fonts, text
from research import results, summary as S
from speech_notes import AUTHORS, make_notes
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether

PDF = FINAL / 'output/pdf/conservative_formula_short_speech_notes.pdf'
MARKDOWN = FINAL / 'presentation/speaker_notes_short.md'


def short_notes(root=results.RESULTS):
    n = S.numbers(root)
    pct = lambda x, d=2: f'{100*float(x):.{d}f} percent'
    scripts = [
        "Hello everyone. We're Yingni Chang and Yikai Shen. Our project tests a simple stock strategy "
        "that combines low volatility, momentum and shareholder payout. We reproduce the paper's "
        "historical results and examine how the strategy performs in more recent data.",

        "Follow the three boxes from left to right. Can we reproduce the paper? How much of the return comes from "
        "familiar market factors? And does the strategy still perform well after trading costs? "
        "These comparisons help us judge both the historical result and its recent relevance.",

        "We use monthly CRSP stock data through 2024, together with delistings, dividends and "
        "factor returns. Earlier observations provide the history needed to begin investing in "
        "1929. We retain disappearing stocks and use historical classifications to avoid looking "
        "only at companies that survived.",

        "Follow the chart from top to bottom: first the largest one thousand stocks with enough "
        "return history, then the five hundred with lower volatility. The two middle boxes rank "
        "momentum and net payout. We average those ranks to choose one hundred equally weighted "
        "stocks and rebalance quarterly. The early sample has fewer eligible stocks, as the "
        "table on the right explains.",

        "Volatility uses thirty-six months of total returns. Momentum uses eleven months of "
        "price returns, skipping the latest month. Net payout combines dividends with changes "
        "in split-adjusted shares, so it includes a proxy for repurchases after issuance.",

        f"Our paper-period annual return is {pct(n['rep_cons_compounded'])}, compared with "
        f"{pct(n['paper_cons_compounded'],1)} in the paper. Volatility is also close. The main "
        f"gap is quarterly turnover: {pct(n['rep_turnover'],1)} versus "
        f"{pct(n['paper_turnover'],0)}. We reproduce the broad pattern, but not every result.",

        "A high return does not automatically mean high alpha. Carhart alpha is the average "
        "return remaining after accounting for market, size, value and momentum exposures. "
        "Adding profitability and investment factors weakens the long-only alpha estimate, "
        "showing that the model matters.",

        "Trading costs reduce the strategy's advantage. For 1990 to 2024, about "
        f"{n['be_alpha|1990–2024']:.0f} basis points per dollar traded eliminates Carhart alpha; "
        f"about {n['be_excess|1990–2024']:.0f} eliminates the average return above the market. "
        "These are break-even cost levels, not return percentages. We charge purchases and sales.",

        "The long history hides differences across periods. Earlier factor-adjusted results "
        "are stronger, while recent estimates are weaker. The 2017 to 2024 sample is only "
        "eight years, so its confidence interval is wide and does not establish positive alpha.",

        f"For 1990 to 2024, annual Carhart alpha is {pct(n['ct_alpha|1990–2024|gross'])} before costs and "
        f"{pct(n['ct_alpha|1990–2024|net10'])} after ten-basis-point costs; neither is significant, "
        "and the FF5 plus momentum alpha is negative even before costs. "
        "Lower volatility is the clearer benefit. Conservative-minus-Speculative compares "
        "the two portfolios; it includes a short leg and is different from holding Conservative alone.",

        "The professor warned against using dividends alone. We also include the change in "
        "adjusted shares to capture net repurchases. The dividends-only comparison performs "
        "worse over the paper period. Share changes remain a proxy, rather than directly "
        "observed buyback spending.",

        "We separate industry allocation from stock selection using the same eligible "
        "universe as a reference. We also test an industry-quota portfolio. The original "
        "paper ranks across industries, so the quota changes the strategy and is an "
        "exploratory comparison, not the baseline rule.",

        "We test whether the signals predict later returns after removing industry effects. "
        "The rank correlations are positive, but that alone does not guarantee a profitable "
        "trading strategy. Factor-mimicking portfolios help examine the exposures; their "
        "gross results do not include a complete trading-cost model.",

        "The long/short experiment suffers severe losses, including bankruptcy for some "
        "original holding-period settings. Linear optimization gives stronger results for "
        "some choices, but we test many settings and recent evidence is weaker. The best "
        "grid result still needs validation on unseen data.",

        "The mean-variance model balances expected return, risk and trading costs. "
        "It uses a regularized covariance estimate because we have many stocks and "
        "a short estimation window. Higher risk aversion lowers realized volatility, "
        "but these long-only portfolios still have substantial market exposure.",

        "The buffer keeps an existing holding while it remains eligible and within "
        f"the best one hundred and fifty ranks. Recent quarterly turnover falls from "
        f"{pct(n['buf_turn_base'],1)} to {pct(n['buf_turn_buf'],1)}. It reduces trading, "
        "but the return improvement is uncertain because its confidence interval includes zero.",

        "We reproduce much of the historical return and risk pattern, although turnover "
        "still differs. We address payout and industry positioning explicitly. In recent "
        "data, lower volatility is more consistent than positive net alpha. The extensions "
        "are useful experiments, but do not establish a superior strategy on unseen data.",

        "We'd appreciate guidance on payout, industry positioning and the turnover gap. "
        "Could we compare our cleaning with your reference? For the weaker recent "
        "extension, should we investigate further or document the result? Which checks "
        "would you prioritize? Thank you.",
    ]
    from research.feedback_summary import extension_notes
    short_extra=[
        "We test zero to thirty basis points in steps of five, with the same holdings. Lower costs improve the 2017-2024 profit, but the US strategy still trails its market over the full period, even before costs.",
        "These wealth paths and rolling twelve-month comparisons show when performance improves or weakens. Rolling alpha is also in the notebook. These overlapping windows describe the sample and do not provide a forecast.",
        "We also let costs change with CRSP bid-ask spreads. We fix a 2016 reference and use only the previous month's spread. The result measures relative liquidity, without estimating our actual execution costs.",
        "For the UK, we apply the same signals to Compustat Global ordinary London shares in pounds. We retain inactive companies and adjust for splits and dividends. Current classifications and incomplete terminal payments remain limitations.",
        "The UK base case beats its own benchmark, but the severe exit-loss stress reverses that advantage. We also show a purchase-tax sensitivity. Different currencies and benchmarks prevent treating this as proof of a country effect.",
    ]
    scripts=scripts[:17]+short_extra
    titles = [note['title'] for note in make_notes(root)]
    if len(scripts) != len(titles):
        raise ValueError('Every slide must have a short script')
    return [{'number': i, 'title': title, 'script': script}
            for i, (title, script) in enumerate(zip(titles, scripts), 1)]


def main():
    notes = short_notes()
    words = sum(len(n['script'].split()) for n in notes)
    intro = (f'Brief script for all 22 slides: approximately {words:,} words, or '
             f'{words/130:.1f} minutes at 130 words per minute. Allow about '
             f'{round(words/130)}-{round(words/130)+2} minutes with pauses, plus questions. '
             'Optional split: Yingni, slides 1-9; Yikai, slides 10-22.')
    lines = ['# Short Speaking Notes for the Conservative Formula', '',
             f'**Authors:** {AUTHORS}', '', intro, '']
    for n in notes:
        lines += [f"## {n['number']}. {n['title']}", '', n['script'], '']
    MARKDOWN.write_text('\n'.join(lines), encoding='utf-8')
    fonts()
    ink = colors.HexColor('#243746')
    body = ParagraphStyle('ShortBody', fontName='ReportSans', fontSize=12,
                          leading=17, textColor=ink, spaceAfter=12)
    heading = ParagraphStyle('ShortHeading', fontName='ReportSansBold', fontSize=14,
                             leading=18, textColor=ink, spaceAfter=9)
    small = ParagraphStyle('ShortIntro', fontName='ReportSans', fontSize=9,
                           leading=12, textColor=colors.HexColor('#526877'), spaceAfter=14)
    story = [Paragraph('Short Speaking Notes for the Conservative Formula', heading),
             Paragraph(escape(AUTHORS), body), Paragraph(escape(intro), small)]
    for i, n in enumerate(notes):
        if i and i % 3 == 0:
            story.append(PageBreak())
        story.append(KeepTogether([
            Paragraph(f"Slide {n['number']} | {escape(n['title'])}", heading),
            Paragraph(escape(text(n['script'])), body), Spacer(1, 14)]))
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('ReportSans', 8)
        canvas.setFillColor(ink)
        canvas.drawString(44, 23, AUTHORS + ' | Short speaking notes')
        canvas.drawRightString(letter[0]-44, 23, str(doc.page))
        canvas.restoreState()
    PDF.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(PDF), pagesize=letter, leftMargin=44, rightMargin=44,
                      topMargin=38, bottomMargin=40, author=AUTHORS,
                      title='Conservative Formula Short Speaking Notes').build(
                          story, onFirstPage=footer, onLaterPages=footer)
    print(f'{len(notes)} short scripts; {words} words.\n{MARKDOWN}\n{PDF}')


if __name__ == '__main__':
    main()
