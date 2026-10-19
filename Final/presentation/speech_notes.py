"""Speaking scripts for the final presentation, using the same saved results as the slides.

Project authors: Yingni Chang and Yikai Shen.
"""
from pathlib import Path
import math
import re

from research import results, summary as S

AUTHORS = "Yingni Chang and Yikai Shen"


def make_notes(root=results.RESULTS):
    n = S.numbers(root)
    load = lambda study, name: results.load(study, name, root=root)[0]
    percent = lambda x, digits=2: f"{100*float(x):.{digits}f} percent"
    plain = lambda x, digits=2: f"{float(x):.{digits}f}"
    notes = []

    def add(title, cue, *paragraphs):
        notes.append({"number": len(notes)+1, "title": title, "cue": cue,
                      "paragraphs": list(paragraphs)})

    add("Replicating the Conservative Formula", "Introduce both authors and the purpose of the project.",
        "Hello everyone. We're Yingni Chang and Yikai Shen. Our project implements the Conservative Formula "
        "proposed by David Blitz and Pim van Vliet. The idea is to combine low volatility, momentum and "
        "shareholder payout in a portfolio of one hundred stocks.",
        "We first try to reproduce the US results over 1929 to 2016, which is the paper's sample. We then "
        "extend the backtest through 2024. The historical comparison is fairly close, but the recent "
        "results are weaker after costs and factor adjustment. I'll explain the rule first, then the "
        "data and results, including the payout and sector issues raised in the assignment.")

    add("What we test", "Explain the distinction between replication and recent performance.",
        "We organize the analysis around three comparisons. First, can we reproduce the paper's "
        "return, volatility and turnover? Second, how much of the return is explained by familiar "
        "equity factors? Third, what happens when we move to recent periods and include trading costs?",
        "These questions matter because a strong result over almost ninety years does not necessarily "
        "mean that the strategy still has a useful advantage today. We use the Carhart model as our "
        "main factor adjustment and compare gross returns with returns at ten and thirty basis "
        "points per dollar traded. The fixed comparison periods were chosen before computing "
        "the post-2016 portfolio results.")

    ex = load("data_audit", "extract_summary.json")["sample"]
    add("The data", "Point to the coverage counts, then emphasize delistings and the early universe.",
        f"We use the full monthly CRSP files from WRDS. After cleaning, the panel has about "
        f"{ex['panel_rows']/1e6:.2f} million security-month observations and {ex['securities']:,} securities. "
        "We combine stock returns with historical company information, delistings, distributions "
        "and the market index. We also use Fama-French factors.",
        "Two choices are especially important. We keep stocks that disappear, including their "
        "terminal returns, instead of looking only at survivors. We also use one common share "
        "class per company to avoid double counting. The earliest portfolio universe has only "
        f"{ex['first_formation_universe_n']} eligible stocks. It first reaches one thousand in June "
        "1964, so the early backtest necessarily uses a smaller universe.")

    add("The portfolio rule", "Follow the selection order on the slide.",
        "At each quarter-end, we first require thirty-six consecutive months of return history. "
        "We then select the largest one thousand eligible stocks by market capitalization. "
        "From this group, we keep the half with the lowest historical volatility.",
        "Within that lower-volatility pool, we rank momentum and net payout favorably, average "
        "the two ranks, and select the best one hundred stocks. Each receives an equal weight. "
        "The holdings then drift with returns for the next three months. We rebalance using "
        "information available at the previous quarter-end. Applying the history requirement "
        "before the size cut is important because reversing that order changes the universe.")

    add("Building the signals", "Explain each signal briefly; spend most of the time on payout.",
        "Volatility is the standard deviation of thirty-six monthly total returns, expressed "
        "in annual units. Momentum compounds eleven monthly price returns and skips the "
        "most recent month. Portfolio performance, in contrast, uses total returns including "
        "distributions and delistings.",
        "Net payout combines dividend yield with the change in adjusted shares. We use the "
        "latest share count relative to its twenty-four-month average. Repurchases increase "
        "the signal, while issuance decreases it. Both prices and shares are split-adjusted, "
        "so a stock split should not create an artificial buyback. The twelve-month dividend "
        "window is a disclosed choice because the paper does not fully specify that part.")

    add("Our results versus the paper", "Point to the return/risk comparison and the growth chart.",
        f"Over the paper's sample, our Conservative portfolio compounds at "
        f"{percent(n['rep_cons_compounded'])} a year before costs, compared with "
        f"{percent(n['paper_cons_compounded'])} in the paper. Our volatility is "
        f"{percent(n['rep_cons_volatility'])}, compared with {percent(n['paper_cons_volatility'])}. "
        "The broad return-and-risk result is therefore close.",
        f"The main unresolved difference is quarterly turnover: we get "
        f"{percent(n['rep_turnover'],1)}, compared with {percent(n['paper_turnover'],1)}. "
        "Some control and regression results differ as well. Share-class choices, capitalization "
        "and dividend estimation could contribute, but we cannot separate their effects. "
        "We leave these gaps visible rather than adjusting the strategy to force a match.")

    add("Factor-adjusted returns", "Define alpha before discussing the factor models.",
        "Alpha here is the return left after accounting for the factors in the regression. "
        "A high raw return can still have little alpha if the portfolio mainly holds "
        "known factor exposures.",
        f"For the Conservative long-only portfolio, annual Carhart alpha over the paper sample "
        f"is {percent(n['att_cons_carhart_alpha'])}. When we use the five Fama-French factors "
        f"plus momentum over 1963 to 2016, the estimate falls to "
        f"{percent(n['att_cons_ff5umd_alpha'])}. Adding profitability and investment changes "
        "the interpretation substantially. We also compare the Conservative-minus-Speculative "
        "contrast with the paper. The post-1963 comparisons are closer than the full-sample "
        "ones, but that does not establish the cause of the remaining difference.")

    add("How costs change the result", "Explain basis points and the single-counted turnover convention.",
        "We charge costs on both purchases and sales. Thirty basis points means a charge "
        "of zero point three percent per dollar traded. Quarterly turnover on the slide "
        "is single-counted, so a purchase and sale are not counted twice in that measure.",
        f"At thirty basis points, the paper-period annual compound return falls to "
        f"{percent(n['rep_cons_net30_compounded'])}. For 1990 to 2024, the break-even "
        f"cost for Carhart alpha is approximately {n['be_alpha|1990–2024']:.0f} basis points. "
        "Break-even means the cost at which the estimated advantage reaches zero. In the "
        "period after 2016, gross excess return and alpha are already nonpositive. "
        "These are flat cost scenarios, not a complete model of historical liquidity or market impact.")

    add("Results by period", "Trace the early-to-recent pattern; do not read every table cell.",
        "The subperiods show why the long history needs to be broken up. The earlier "
        "Carhart estimates are stronger, while the recent estimates are weaker. The "
        "rolling plots show a similar pattern, although adjacent windows overlap "
        "and should not be treated as independent observations.",
        f"For 2017 to 2024, gross Carhart alpha is {percent(n['ct_alpha|2017–2024|gross'])}. "
        f"Its ninety-five-percent interval runs from "
        f"{percent(n['ct_alpha_lo|2017–2024|gross'])} to {percent(n['ct_alpha_hi|2017–2024|gross'])}. "
        "That interval is wide because the sample contains only eight years. "
        "We do not find strong evidence of outperformance in that period, but an "
        "insignificant estimate is not proof that expected alpha is exactly zero.")

    key = "1990–2024|net30"
    add("The recent sample: 1990–2024", "Give the net-alpha estimate, interval and lower-risk result.",
        f"This is our main recent comparison. After thirty-basis-point trading costs, "
        f"annual Carhart alpha is {percent(n['ct_alpha|'+key])}. The ninety-five-percent "
        f"interval is roughly {percent(n['ct_alpha_lo|'+key])} to {percent(n['ct_alpha_hi|'+key])}, "
        "so it includes zero. That makes a strong claim about recent factor-adjusted "
        "outperformance difficult to support.",
        "The more consistent benefit is lower volatility than the market. The "
        "Conservative-minus-Speculative contrast still has a stronger result, "
        "but that includes shorting the Speculative portfolio. It is a different "
        "comparison from holding the Conservative portfolio alone, and its "
        "attribution result does not include actual borrow or financing costs.")

    pc = load("professor_checks", "payout_comparison.csv")
    base = S.one(pc, period="1929–2016", strategy="Baseline NPY")
    div = S.one(pc, period="1929–2016", strategy="Dividends-only counterfactual")
    add("Dividends and share repurchases", "Emphasize the assignment's payout warning and the matched comparison.",
        "This is one of the specific issues raised in the assignment. Dividend yield "
        "alone misses the indirect payout from repurchases. For example, with a "
        "three-percent dividend yield, ninety adjusted shares today and a "
        "one-hundred-share average, the net payout signal is thirteen percent. "
        "Issuance works in the opposite direction.",
        f"In the matched backtest, the net-payout rule earns {percent(base.compounded)} "
        f"gross annually, compared with {percent(div.compounded)} using dividends alone. "
        "We hold the other rules constant so that we are comparing the payout ranking. "
        "This shows that the share-count term matters. It is still a proxy for net "
        "repurchases after issuance, not directly observed buyback cash spending or "
        "a causal estimate of the effect of buybacks.")

    a = S.one(load("professor_checks", "sector_attribution.csv"), period="1929–2016")
    quota = S.one(pc, period="1929–2016", strategy="Sector quota variant")
    add("Industry allocation and stock selection", "Explain the reference universe and then the industry quota rule.",
        "For sector positioning, we use Fama-French twelve industries. We compare "
        "our portfolio with a cap-weighted reference from the same formation universe, "
        "so a broad-market universe difference does not get mistaken for industry allocation.",
        f"Over the paper sample, industry allocation contributes about "
        f"{percent(a.allocation_annual)} a year and stock selection about "
        f"{percent(a.selection_annual)}. A separate universe-to-market term completes "
        "the monthly identity. These are arithmetic contributions, not contributions to CAGR.",
        "We also follow the course's quota idea: if an industry contains fifteen percent "
        "of universe stocks, it receives about fifteen of the one hundred holdings. "
        f"That variant earns {percent(quota.compounded)} gross annually. It changes "
        "the paper's global screen and was considered after the baseline results, "
        "so we treat it as an exploratory comparison.")

    add("Signal tests", "Define IC and explain why rank correlation differs from a mean return spread.",
        "We next examine the signals separately. We remove industry means, standardize "
        "the exposures and clip extremes. The information coefficient, or IC, is "
        "the rank correlation between a signal and later industry-adjusted returns.",
        f"The composite's one-month IC is about {plain(n['ic_comp_h1'],3)}. "
        "We also look at deciles, persistence and longer holding horizons. A positive "
        "rank correlation does not always imply a strong mean spread when returns "
        "are skewed. The factor-mimicking portfolios help separate signal exposures "
        "from industry, size and historical Fama-French controls. Their gross "
        "information ratio falls as we average more old portfolios, along with turnover. "
        "They are diagnostic portfolios with leverage, rather than a fully costed trading strategy.")

    add("Long/short and linear optimization", "Separate the failed trading experiment from the optimizer grid.",
        "The long/short exercise buys the top composite decile and sells the bottom "
        "decile. We compare holding periods, trading costs and monthly borrow fees. "
        "The original buy-and-hold cohorts lose all capital in the early data for "
        "several holding periods. We then examine monthly reweighting, which still "
        "has an extremely deep drawdown. That alternative was chosen after seeing the losses.",
        "The linear optimizer gives stronger-looking recent results for some settings. "
        "It caps individual stocks, constrains industries and limits turnover. "
        f"But {n['opt_ci_9024_text']} "
        "for the four displayed recent examples, and those intervals are unadjusted "
        "for testing many settings. The post-2016 estimates are weaker. We would "
        "need an unseen test before treating the best grid result as reliable.")

    mv = load("mean_variance", "summary.csv")
    low = S.one(mv, period="1990–2024", risk_aversion=5)
    high = S.one(mv, period="1990–2024", risk_aversion=20)
    add("Mean-variance portfolios", "Use the table to compare the two risk-aversion settings.",
        "The quadratic model adds portfolio variance to the objective, alongside "
        "expected return and trading cost. We estimate covariance using the last "
        "thirty-six monthly returns. With about one thousand stocks and only "
        "thirty-six observations, sample covariance needs regularization, so "
        "we combine it equally with diagonal covariance.",
        f"For 1990 to 2024, risk aversion five gives net CAGR of "
        f"{percent(low.compounded)} and volatility of {percent(low.volatility)}. "
        f"At risk aversion twenty, those figures are {percent(high.compounded)} "
        f"and {percent(high.volatility)}. More risk aversion lowers realized "
        "volatility, but market correlations remain high. These long-only "
        "portfolios are not market-neutral. We chose these settings after "
        "examining the baseline and have not established that they are optimal.")

    add("A buffer to reduce trading", "Point to the turnover reduction and the confidence interval.",
        "The buffer asks whether we need to sell a holding immediately when its "
        "rank slips below one hundred. We keep it while it remains eligible "
        "and among the best one hundred and fifty ranks, then fill vacancies. "
        "We fixed that buffer size before testing the variant.",
        f"Quarterly turnover falls from {percent(n['buf_turn_base'],1)} to "
        f"{percent(n['buf_turn_buf'],1)}. The net paired difference is "
        f"{percent(n['buf_diff'])} a year, but its interval includes zero. "
        "The modification reduces trading, while also changing holdings, "
        "so we cannot attribute the whole return difference to costs. We "
        "view it as a useful trading experiment, not proof of a better signal.")

    add("What we conclude", "Pause on the main conclusion and the unresolved turnover difference.",
        "Our implementation reproduces much of the paper's historical return "
        "and risk pattern, but it is not an exact replication. Turnover and "
        "some regression results still differ. We have also checked the two "
        "issues highlighted in the assignment: net payout includes the "
        "adjusted share-count term, and industry positioning is measured "
        "and tested separately.",
        "For recent data, lower volatility is more consistent than positive "
        "net alpha. The buffer and optimizers change trading and risk, "
        "but their results do not yet show a stronger strategy on unseen "
        "data. Our conclusion is that this is a useful, understandable "
        "factor portfolio, with important limits to a claim of persistent outperformance.")

    add("Questions for the professor", "Invite guidance; pause after each question and allow discussion.",
        "We would appreciate guidance on a few implementation choices. Is our twelve-month "
        "dividend yield plus the share-count term based on a twenty-four-month average the "
        "intended payout definition? Should our main result keep the paper's global ranking "
        "or use an industry adjustment? And which turnover convention should we use "
        "when comparing our higher turnover with the paper?",
        "You mentioned sharing the data-cleaning work. Could we compare our dividends, "
        "split adjustments and delistings with your reference? Finally, should we investigate "
        "the weaker recent extension further, or document it as a finding? Which checks "
        "would you prioritize? Thank you.")

    transitions = [
        "Let me start with what we wanted to test.",
        "Those comparisons depend on the data, so I'll turn to the CRSP inputs.",
        "With those files cleaned, the selection rule is fairly simple.",
        "I'll show how we calculate the three inputs to those ranks.",
        "Now we can compare the backtest with the published figures.",
        "Close raw returns are only part of the comparison; let's look at factor-adjusted returns.",
        "Trading costs are another reason gross return can be misleading.",
        "Let's look at how the estimates change across periods.",
        "We will now focus on the recent sample in more detail.",
        "Next are the two implementation checks highlighted in the assignment.",
        "The other concern is industry positioning.",
        "We also test the signals outside the original stock-selection rule.",
        "That leads to the trading and portfolio-construction experiments.",
        "The next model adds a covariance penalty.",
        "Finally, we test a simpler change aimed at reducing turnover.",
        "These comparisons lead us to the main conclusion.",
        "We'd like to finish with a few questions about implementation and next steps.",
        "",
    ]
    for note, transition in zip(notes, transitions): note["transition"] = transition
    from research.feedback_summary import extension_notes
    extra=extension_notes(root)
    notes=notes[:17]+extra+notes[17:]
    notes[16]['transition']='We now turn to the follow-up work suggested after the presentation.'
    notes[-1]['paragraphs']=["The remaining questions concern the turnover difference and better UK inputs. We would like historical country and exchange classifications and observed terminal payments. We also need guidance on a national benchmark and UK factors for a common-currency comparison. Finally, we can refine costs by traded stock and order size. Thank you."]
    for i,note in enumerate(notes,1):note['number']=i
    return notes


def question_answers(root=results.RESULTS):
    n = S.numbers(root)
    return [
        ("Did you reproduce the paper exactly?",
         f"No. Return and volatility are close, but quarterly turnover is {100*n['rep_turnover']:.1f}% "
         f"versus {100*n['paper_turnover']:.0f}%, and some regression/control results differ. "
         "We cannot isolate the cause without the authors' exact cleaned inputs and conventions."),
        ("How do you account for share repurchases?",
         "Payout is dividend yield plus one minus latest split-adjusted shares divided by their "
         "24-month average. Repurchases raise the signal; issuance lowers it. We check split "
         "neutrality and compare the rule with dividends alone. Share changes are a net proxy, not reported buyback cash flow."),
        ("Why isn't the paper baseline sector-neutral?",
         "The paper explicitly compares scores across sectors. We preserve that rule for the "
         "replication and separately use industry-adjusted diagnostics, allocation/selection "
         "attribution and a count-proportional FF12 quota strategy."),
        ("Does an insignificant alpha mean the strategy does not work?",
         "It means the estimate does not provide strong evidence of nonzero factor-adjusted "
         "return at the chosen confidence level. It does not prove expected alpha is exactly zero. "
         "The strategy can still provide lower volatility and exposure to known factors."),
        ("Which experiments use an unseen sample?",
         "The main comparison periods were fixed before computing post-2016 portfolio returns. "
         "The later sector and quadratic experiments, and the monthly-reweighted long/short, "
         "were considered after results were seen. We do not claim an unseen validation sample for those variants."),
        ("Are the capacity and cost assumptions realistic?",
         "They are simplified scenarios. Costs are proportional to traded dollars, sometimes scaled "
         "by size and volatility. Capacity uses monthly volume and a 10% participation assumption, "
         "normalized to 2024 market size. The follow-up also uses lagged quoted spreads and a separate UK purchase-tax scenario. Market impact, daily scheduling and actual borrow availability are omitted."),
    ]


def word_count(note):
    return len(re.findall(r"\S+", " ".join(note["paragraphs"]) + " " + note["transition"]))


def plain_notes(note):
    body = "\n\n".join(note["paragraphs"])
    if note["transition"]: body += "\n\nTransition: " + note["transition"]
    return body + "\n\nPresenter cue: " + note["cue"]


def write_markdown(notes, destination, root=results.RESULTS):
    words = sum(word_count(note) for note in notes)
    lines = ["# Speech Notes for the Conservative Formula Presentation", "",
             f"**Authors:** {AUTHORS}", "",
             f"The read-aloud script contains approximately {words:,} words. At 130 words per minute, "
             f"that is about {words/130:.0f} minutes before pauses and discussion of charts. "
             f"Allow roughly {math.floor(words/130)}-{math.ceil(words/130+2)} minutes with short pauses.", "",
             "Presenter cues are reminders, not spoken lines. An optional split is Yingni on slides 1-9 "
             "and Yikai on slides 10-23; change this to suit your delivery.", ""]
    for note in notes:
        seconds = round(word_count(note)/130*60)
        lines += [f"## {note['number']}. {note['title']}", "",
                  f"**Approximate speaking time:** {seconds} seconds, plus pauses.", "",
                  f"**Presenter cue:** {note['cue']}", ""]
        for paragraph in note["paragraphs"]: lines += [paragraph, ""]
        if note["transition"]: lines += ["**Transition:** " + note["transition"], ""]
    lines += ["# Questions to Prepare For", ""]
    for question,answer in question_answers(root):
        lines += [f"**{question}**", "", answer, ""]
    Path(destination).write_text("\n".join(lines), encoding="utf-8")
