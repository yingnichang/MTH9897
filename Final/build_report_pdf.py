"""Generate the written final report from verified aggregate results.

Project authors: Yingni Chang and Yikai Shen.

Run from Final: python build_report_pdf.py
Output: output/pdf/conservative_formula_report.pdf
No licensed stock-level observations are read or included in the PDF.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

from research import results, summary as S

ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT / "output/pdf/conservative_formula_report.pdf"
NAVY = colors.HexColor("#183447")
TEAL = colors.HexColor("#087C86")
INK = colors.HexColor("#243746")
MUTED = colors.HexColor("#526877")
PALE = colors.HexColor("#EFF6F7")
WIDTH = letter[0] - 88


def text(value):
    """ASCII punctuation avoids ambiguous minus/dash glyphs in submitted PDFs."""
    return str(value).translate(str.maketrans({
        "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2011": "-",
        "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
    }))


def pct(value, digits=2):
    return "n/a" if pd.isna(value) else f"{float(value)*100:.{digits}f}%"


def number(value, digits=2):
    return "n/a" if pd.isna(value) else f"{float(value):.{digits}f}"


def interval(low, high):
    return f"[{pct(low)}, {pct(high)}]"


def fonts():
    directory = Path("C:/Windows/Fonts")
    if (directory / "arial.ttf").exists():
        regular, bold = directory / "arial.ttf", directory / "arialbd.ttf"
    else:
        import matplotlib
        directory = Path(matplotlib.get_data_path()) / "fonts/ttf"
        regular, bold = directory / "DejaVuSans.ttf", directory / "DejaVuSans-Bold.ttf"
    pdfmetrics.registerFont(TTFont("ReportSans", str(regular)))
    pdfmetrics.registerFont(TTFont("ReportSansBold", str(bold)))
    pdfmetrics.registerFontFamily("ReportSans", normal="ReportSans", bold="ReportSansBold",
                                italic="ReportSans", boldItalic="ReportSansBold")


class WrittenReport:
    def __init__(self, result_root):
        self.root = Path(result_root)
        self.manifest = results.manifest(self.root)
        if self.manifest.get("last_run", {}).get("status") != "complete":
            raise ValueError("The research run must complete before a final report is generated")
        for key in self.manifest["files"]:
            results.path(*key.split("/", 1), root=self.root)
        self.numbers = S.numbers(self.root)
        self.story = []
        fonts()
        styles = getSampleStyleSheet()
        self.styles = {
            "body": ParagraphStyle("ReportBody", fontName="ReportSans", fontSize=10.1,
                                   leading=14, textColor=INK, spaceAfter=8),
            "small": ParagraphStyle("ReportSmall", fontName="ReportSans", fontSize=8.5,
                                    leading=11.5, textColor=MUTED, spaceAfter=7),
            "h1": ParagraphStyle("ReportH1", fontName="ReportSansBold", fontSize=19,
                                 leading=23, textColor=NAVY, spaceAfter=14),
            "h2": ParagraphStyle("ReportH2", fontName="ReportSansBold", fontSize=11.5,
                                 leading=15, textColor=TEAL, spaceBefore=5, spaceAfter=7),
            "title": ParagraphStyle("ReportTitle", fontName="ReportSansBold", fontSize=28,
                                    leading=33, textColor=NAVY, spaceAfter=16),
            "cell": ParagraphStyle("ReportCell", fontName="ReportSans", fontSize=8.3,
                                   leading=10.8, textColor=INK),
            "head": ParagraphStyle("ReportHead", fontName="ReportSansBold", fontSize=8.3,
                                   leading=10.8, textColor=colors.white),
            "code": ParagraphStyle("ReportCode", parent=styles["Code"], fontName="Courier",
                                   fontSize=8.5, leading=12, textColor=INK, spaceAfter=9),
        }

    def load(self, study, name):
        return results.load(study, name, root=self.root)[0]

    def p(self, value, style="body"):
        self.story.append(Paragraph(text(value), self.styles[style]))

    def heading(self, title, first=False):
        if not first:
            self.story.append(PageBreak())
        self.p(title, "h1")

    def sub(self, title):
        self.p(title, "h2")

    def table(self, headers, rows, widths=None, caption=None):
        # Input tables contain aggregate observations only; never accept stock identifier headers.
        if results.security_headers(headers):
            raise ValueError("The report cannot contain stock-level identifier columns")
        values = [[Paragraph(escape(text(x)), self.styles["head"]) for x in headers]]
        values += [[Paragraph(escape(text(x)), self.styles["cell"]) for x in row] for row in rows]
        widths = [WIDTH * x for x in widths] if widths else [WIDTH / len(headers)]*len(headers)
        t = Table(values, colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F8")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, -1), (-1, -1), .5, colors.HexColor("#CCD8DE")),
        ]))
        self.story.extend([t, Spacer(1, 9)])
        if caption:
            self.p(caption, "small")

    def figure(self, study, name, caption, height=225):
        path = results.path(study, name, root=self.root)
        with PILImage.open(path) as im:
            ratio = im.width / im.height
        width = min(WIDTH, height*ratio)
        actual_height = width/ratio
        im = Image(str(path), width=width, height=actual_height, hAlign="CENTER")
        self.story.append(KeepTogether([im, Spacer(1, 5),
            Paragraph(text(caption), self.styles["small"])]))

    def box(self, value):
        t = Table([[Paragraph(text(value), self.styles["body"])]], colWidths=[WIDTH])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE),
                              ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#BCD7DA")),
                              ("LEFTPADDING", (0, 0), (-1, -1), 10),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                              ("TOPPADDING", (0, 0), (-1, -1), 9),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        self.story.extend([t, Spacer(1, 10)])

    def code(self, value):
        self.story.append(Preformatted(value, self.styles["code"]))

    def content(self):
        N = self.numbers
        self.p("MTH 9897 SYSTEMATIC TRADING | PROJECT 8", "small")
        self.p("The Conservative Formula", "title")
        self.p("A critical replication on CRSP, 1929-2024", "h1")
        self.p("<b>Yingni Chang and Yikai Shen</b><br/>Final written report | October 13, 2026")
        self.p("Reference: David Blitz and Pim van Vliet (2018), <i>The Conservative Formula: "
               "Quantitative Investing Made Easy</i>, The Journal of Portfolio Management 44(7); "
               "working paper SSRN 3145152.")
        self.sub("Abstract")
        self.p(f"This project reproduces a quarterly, equal-weighted 100-stock strategy combining low "
               f"volatility, price momentum and net payout yield. Over the paper's 1929-2016 sample, "
               f"the CRSP replication earns {pct(N['rep_cons_compounded'])} compounded annually "
               f"with {pct(N['rep_cons_volatility'])} volatility, versus the paper's "
               f"{pct(N['paper_cons_compounded'])} and {pct(N['paper_cons_volatility'])}. "
               "The project then tests factor attribution, performance decay and trading costs, "
               "and implements the assignment's diagnostics and construction extensions.")
        key = "1990–2024|net30"
        self.box(f"<b>Main conclusion.</b> In 1990-2024, net of 30 bps per dollar traded, annual "
                 f"Carhart alpha is {pct(N['ct_alpha|'+key])}, with a 95% interval "
                 f"{interval(N['ct_alpha_lo|'+key],N['ct_alpha_hi|'+key])}. "
                 "The evidence does not establish persistent recent outperformance after known "
                 "factors and costs. The formula offers a simple way to hold several established premia.")
        self.p("The professor's two concerns receive explicit tests: net payout includes both dividends "
               "and adjusted-share repurchases/issuance, and industry allocation is separated from "
               "stock selection. A sector quota variant is reported separately because it changes "
               "the paper's global selection rule. The executed notebook remains the required "
               "primary deliverable; this PDF is a readable companion.")
        self.table(["Scope", "Evidence"], [
            ["Paper replication", "1929-2016; 1,056 monthly observations"],
            ["Extended research", "1929-2024; 1,152 monthly observations"],
            ["Verification", "12 studies; 85 verified aggregate result files; 139 tests passed"],
        ], [.27, .73])

        self.heading("1. Research question and test design")
        self.p("The paper asks whether a small set of intuitive signals can capture major equity "
               "factor premia without a complex model. Its Conservative portfolio combines low "
               "historical return volatility with strong price momentum and high net payout. "
               "Its Speculative mirror uses the high-volatility half and weak combined scores.")
        self.table(["Question", "Test and interpretation"], [
            ["Can the paper be reproduced?", "Compare gross return, risk, turnover, control portfolios "
             "and regression alphas on 1929-2016 under the paper's definitions."],
            ["Is return explained by known factors?", "Carhart four-factor alpha is primary. "
             "Fama-French five factors plus momentum is a robustness check from July 1963."],
            ["Has performance weakened?", "Fixed subperiods and rolling 120-month estimates. "
             "1990-2024 is the headline; 2017-2024 is the post-paper sample."],
            ["What survives costs?", "Returns at 10 and 30 bps per dollar traded and break-even "
             "costs for market excess return and Carhart alpha."],
        ], [.31, .69])
        self.sub("Periods, uncertainty and interpretation")
        self.p("The documented primary design fixes 1929-1962, 1963-1989, 1990-2016 and 2017-2024, "
               "plus the combined recent period 1990-2024. The post-paper period contains only "
               "96 months. Newey-West intervals account for serial dependence; the portfolio "
               "regressions use 12 lags. Some performance intervals use moving-block bootstrap "
               "resampling. Overlapping diagnostic horizons use longer lag choices recorded "
               "in their result tables.")
        self.p("Annual compound return is (product of 1 + monthly return) raised to 12/T, minus 1. "
               "Annual arithmetic return is 12 times the monthly mean; volatility is the monthly "
               "sample standard deviation times the square root of 12. These measures are kept "
               "distinct. Information ratios divide annualized active return by tracking error; "
               "the long/short exercise instead reports excess over collateral risk-free return.")
        self.box("<b>Research status.</b> The original critical tests and rank-buffer choice were "
                 "documented before their results. The additional payout/sector comparisons, "
                 "FF3 stock-beta controls and quadratic optimizer were added during the final "
                 "review after the baseline was seen. They are exploratory. The observed "
                 "2017-2024 data are not an unseen validation set for those additions.")
        self.p("This report covers the US assignment. It does not reproduce the paper's "
               "international FactSet samples, and CRSP alone does not supply the book-equity "
               "inputs needed for a separate Value control.")

        self.heading("2. CRSP inputs and data management")
        extract = self.load("data_audit", "extract_summary.json")
        sample = extract["sample"]
        self.p(f"Full CRSP legacy web exports from WRDS supply the monthly history from December "
               f"1925 through December 2024. The normalized panel contains "
               f"{sample['panel_rows']:,} security-months and {sample['securities']:,} securities. "
               f"There are {sample['eligible_rows']:,} eligible observations. Source receipts, "
               "query metadata, input counts and SHA-256 hashes identify the extract; a CRSP "
               "release identifier was not provided.")
        self.table(["Input", "Use"], [
            ["Monthly stock file", "Total/price returns, price, shares, monthly volume and split factors"],
            ["Stock names/history", "Time-varying share codes, exchanges, company identifiers and SIC industries"],
            ["Delisting file", "Terminal event dates, codes and delisting returns"],
            ["Distribution file", "Independent checks of implied cash dividends and corporate actions"],
            ["Monthly index file", "CRSP value-weighted benchmark and total market size for capacity normalization"],
            ["FF3, momentum and FF5", "Risk-free rate and factor-attribution regressions"],
        ], [.30, .70])
        self.sub("Cleaning choices")
        self.p("The universe uses common-share codes 10/11 and exchange codes 1/2/3. Each month "
               "retains the largest common share class per company, avoiding double counting. "
               "Historical names are joined at their effective dates. Terminal events and "
               "delisted securities remain in the holding-period returns; later rows following "
               "the terminal event are removed. There are no duplicate security-months or "
               "duplicate eligible company-months.")
        ds = sample["delist_sources"]
        self.table(["Data convention", "Count or rule"], [
            ["Terminal events", f"{sample['terminal_rows']:,}: {ds['observed']:,} observed returns; "
             f"{ds['imputed_shumway']:,} imputed; {ds['missing_set_zero']:,} set to zero"],
            ["Performance delisting imputation", "-30% for NYSE/AMEX and -55% for Nasdaq where the documented rule applies"],
            ["Missing held returns", f"Stale-price carry or an in-gap price ratio; "
             f"{sample['universe_holding_stale_carry_months']:,} stale holding months in the audited universe"],
            ["Historical universe coverage", f"{sample['first_formation_universe_n']} names at December "
             f"1928; first full 1,000-name universe at {sample['first_formation_with_full_universe']}"],
        ], [.40, .60])
        self.p("Missing returns remain missing in historical signal windows. The held-return "
               "convention is separate: it keeps a position rather than silently dropping a "
               "missing holding observation. The dividend and delisting audits document the "
               "limits of these conventions, especially in early data.", "small")

        self.heading("3. Signals and baseline construction")
        self.sub("Point-in-time signal definitions")
        self.code("Adjusted price P[t] = abs(PRC[t]) / CFACPR[t]\n"
                  "Adjusted shares S[t] = SHROUT[t] * CFACSHR[t]\n"
                  "Volatility = sd(RET_total[t-35], ..., RET_total[t]) * sqrt(12)\n"
                  "Momentum = product(1 + RET_price[t-11], ..., RET_price[t-1]) - 1\n"
                  "Dividend yield = sum(D_adj[t-11], ..., D_adj[t]) / P[t]\n"
                  "Net payout = dividend yield + 1 - S[t] / mean(S[t-23], ..., S[t])")
        self.p("Price momentum contains 11 monthly returns and excludes the latest month. "
               "Volatility uses 36 consecutive monthly total returns. Implied adjusted cash "
               "dividends use total return minus price return times the preceding adjusted "
               "price. The 12-month dividend window and 24-month share average including the "
               "formation month are disclosed implementation conventions.")
        self.table(["Order", "Quarter-end action"], [
            ["1", "Apply eligibility, positive capitalization, non-terminal status and 36-month history."],
            ["2", "Choose the largest 1,000 eligible stocks by security capitalization, or all if fewer exist."],
            ["3", "Retain the lower-volatility half; then require complete momentum and net payout signals."],
            ["4", "Rank momentum and net payout favorably within the pool; average the two ranks."],
            ["5", "Select the best 100, resolve ties deterministically, and assign 1% weights."],
            ["6", "Hold the next three months; weights drift, with terminal proceeds held as cash earning RF."],
        ], [.10, .90])
        self.p("The history screen precedes the size cut, as described by the paper. Selection "
               "uses information available at the quarter-end before the first holding month. "
               "Signals do not change when later input values are changed in the tests. "
               "Baseline factor ranks are compared across industries: the paper explicitly "
               "uses global scores. Industry neutrality is an assignment extension.")
        self.sub("Trading and costs")
        self.p("Trading cost is charged on total absolute changes in stock weights, with initial "
               "investment included in NAV. Published quarterly turnover is single-counted, "
               "one half of this traded notional, excluding the initial allocation. At a "
               "flat cost c, net monthly return is (1 - c times traded notional) times "
               "(1 + gross return), minus 1. This timing differs slightly from subtracting "
               "an annual cost estimate from CAGR.")

        self.heading("4. Replication over the paper sample")
        self.p(f"The Conservative baseline earns {pct(N['rep_cons_compounded'])} gross annually "
               f"with {pct(N['rep_cons_volatility'])} volatility over 1929-2016. "
               f"The market earns {pct(N['rep_mkt_compounded'])}; the Speculative control earns "
               f"{pct(N['rep_spec_compounded'])} with {pct(N['rep_spec_volatility'])} volatility. "
               "The risk/return contrast is reproduced, but exact numerical equality is not claimed.")
        target = self.load("paper_targets", "table1_vs_paper.csv")
        rows = []
        for portfolio in ["Formula", "Market", "Small", "Momentum", "Lowvol", "NPY"]:
            ret = S.one(target, row="Return (compounded)", column=portfolio)
            vol = S.one(target, row="Volatility", column=portfolio)
            rows.append([portfolio, pct(ret.paper), pct(ret.ours), pct(vol.paper), pct(vol.ours)])
        self.table(["Portfolio", "Paper CAGR", "CRSP CAGR", "Paper vol.", "CRSP vol."], rows,
                   [.24, .19, .19, .19, .19], "Gross returns; 1,056 months. Value is excluded because "
                   "book equity is unavailable in the CRSP-only inputs.")
        self.figure("replication", "fig3.png", "Growth of $100 using monthly gross returns. "
                    "A logarithmic scale makes long-sample compound growth comparable.", height=238)
        self.box(f"<b>Unresolved turnover gap.</b> Quarterly single-counted turnover is "
                 f"{pct(N['rep_turnover'],1)}, versus {pct(N['paper_turnover'],1)} in the paper. "
                 "The paper's implementation and exact measure are not fully specified. "
                 "The result is retained rather than tuned to force a match.")

        self.heading("5. Net payout and the repurchase check")
        self.p("The professor highlighted an important failure mode: dividend yield alone "
               "does not represent shareholder payout. A reduction in adjusted shares raises "
               "the payout signal; net issuance lowers it. A split must not alter the adjusted "
               "share count. With dividend yield of 3%, 90 current adjusted shares and a "
               "100-share average, net payout is 13%.")
        comparison = self.load("professor_checks", "payout_comparison.csv")
        chosen = comparison.loc[comparison.period.eq("1929–2016")]
        self.table(["Strategy", "Gross CAGR", "Net 30 CAGR", "Quarterly turnover"], [
            [r.strategy, pct(r.compounded), pct(r.net30_compounded), pct(r.turnover_quarter)]
            for r in chosen.itertuples()], [.43, .18, .18, .21])
        base = S.one(comparison, period="1929–2016", strategy="Baseline NPY")
        self.p(f"The paired net-return difference between the original NPY rule and dividends "
               f"alone is {pct(base.paired_npy_minus_div_net30_mean)} per year in arithmetic "
               f"terms, with a Newey-West 95% interval "
               f"{interval(base.paired_ci_low,base.paired_ci_high)}. Universe, low-volatility "
               "pool, complete-case membership, momentum, portfolio size, weights, dates "
               "and costs are matched; only the payout ranking is replaced.")
        components = self.load("professor_checks", "payout_components.csv")
        self.table(["Period", "Dividend yield", "Net share proxy", "NPY", "Overlap with dividends-only"], [
            [r.period, pct(r.dividend_yield), pct(r.net_repurchase_proxy), pct(r.npy),
             pct(r.baseline_dividends_only_overlap,1)]
            for r in components.loc[components.period.isin(["1929–2016","1990–2024","2017–2024"])].itertuples()],
                   [.20, .19, .19, .16, .26], "Formation averages among baseline holdings; "
                   "these are signal components, not realized cash payout returns.")
        self.sub("Checks and limitations")
        self.p("Synthetic cases check buybacks, issuance and split neutrality. Direct "
               "recalculation on 1,200 actual observations verifies the 36-, 12- and "
               "24-month windows, with maximum differences below 8.0e-15. Implied dividends "
               "are separately compared with CRSP distributions; approximately 96.8%-99.85% "
               "of checkable ordinary-cash cases reconcile by decade.")
        self.box("Adjusted share changes capture net repurchases after issuance; they are "
                 "not observed buyback cash expenditures. Other corporate actions can also "
                 "change shares. Dividend timing, special distributions and incomplete "
                 "observations remain sources of uncertainty. The matched comparison "
                 "shows a material signal difference, not a causal estimate of buybacks.")

        self.heading("6. Industry positioning and stock selection")
        self.p("The baseline is compared with a capitalization-weighted reference drawn "
               "from the same formation universe. Constituents and industry labels are "
               "fixed for each quarter; both portfolios drift with returns and move terminal "
               "proceeds to cash. This avoids confusing a broad-market universe difference "
               "with industry allocation.")
        self.code("Baseline - CRSP market\n"
                  "  = industry allocation + stock selection\n"
                  "    + reference universe - CRSP market\n"
                  "Allocation = sum[(w_portfolio - w_reference) * r_industry]\n"
                  "Selection = sum[w_portfolio * (r_portfolio_ind - r_industry)]")
        self.p("The stock-selection term includes the allocation/selection interaction. "
               "The identity is reconciled monthly, including cash. Annual contributions "
               "are 12 times the monthly mean, rather than contributions to compound return.")
        attribution = self.load("professor_checks", "sector_attribution.csv")
        self.table(["Period", "Allocation", "Selection", "Universe bridge", "Total excess"], [
            [r.period, pct(r.allocation_annual), pct(r.selection_annual),
             pct(r.universe_minus_market_annual), pct(r.baseline_minus_market_annual)]
            for r in attribution.loc[attribution.period.isin(["1929–2016","1990–2024","2017–2024"])].itertuples()],
                   [.20, .18, .18, .22, .22], "Annual arithmetic contributions. They describe "
                   "portfolio positioning and do not identify causal industry effects.")
        self.sub("Separate sector quota experiment")
        quotas = self.load("professor_checks", "sector_quota_checks.csv")
        comparison = self.load("professor_checks", "payout_comparison.csv")
        original = S.one(comparison, period="1929–2016", strategy="Baseline NPY")
        quota_result = S.one(comparison, period="1929–2016", strategy="Sector quota variant")
        self.p("Following the professor's Enhanced Momentum example, the variant allocates "
               "100 slots in proportion to the universe's FF12 industry stock counts. "
               "Largest-remainder rounding sets integer quotas. Within each industry "
               "it retains the low-volatility half, then ranks momentum and net payout "
               "and fills its quota. Stocks receive equal weights.")
        self.p(f"All {len(quotas)} formations hold 100 names. The largest deviation from an "
               f"industry's count-proportional target is "
               f"{100*quotas.max_abs_industry_weight_minus_universe_count_weight.max():.2f} "
               f"percentage points. The variant earns {pct(quota_result.compounded)} gross "
               f"annually over 1929-2016 versus {pct(original.compounded)} for the original "
               "baseline, with more turnover. These values "
               "are also shown in the matched strategy table on page 6.")
        self.box("Industry neutrality is not silently imposed on the paper baseline. "
                 "The quota variant changes the global volatility screen and is exploratory. "
                 "FF12 industries are the available US grouping used for both the diagnostics "
                 "and these sector-positioning checks.")

        self.heading("7. Factor attribution and known premia")
        self.p("Monthly portfolio excess returns are regressed on the market factor, then "
               "size/value, momentum and the FF5 profitability/investment factors. "
               "Carhart is the primary attribution model. FF5 plus momentum uses July "
               "1963 onward, so its result is not a full 1929-2016 estimate.")
        attribution = self.load("attribution", "table2.csv")
        rows = []
        for portfolio, model in [("Conservative","CAPM"),("Conservative","Carhart"),
                                 ("Conservative","FF5+UMD"),("CMS","CAPM"),
                                 ("CMS","Carhart"),("CMS","FF5+UMD")]:
            r = S.one(attribution, returns="gross", portfolio=portfolio, model=model)
            rows.append([portfolio, model, pct(r.alpha_annual), number(r.alpha_t_nw), str(int(r.n))])
        self.table(["Portfolio", "Model", "Annual alpha", "NW t", "Months"], rows,
                   [.25, .22, .23, .15, .15], "CMS is the Conservative minus Speculative contrast. "
                   "Gross rows compare with the paper; confidence inference uses Newey-West errors.")
        self.p(f"The Conservative portfolio's FF5-plus-momentum alpha is "
               f"{pct(N['att_cons_ff5umd_alpha'])} (NW t {number(N['att_cons_ff5umd_t'])}). "
               "The reduction in alpha when profitability and investment are included is "
               "consistent with the formula capturing known factor exposures, rather than "
               "creating an independent source of return.")
        self.sub("Replicating the paper's regression tables")
        table2 = self.load("paper_targets", "table2_vs_paper.csv")
        rows = []
        for panel, model in [("A","CAPM"),("A","Carhart"),("B","CAPM"),("B","FF3"),
                             ("B","FF5"),("B","FF5 + MOM")]:
            r = S.one(table2, panel=panel, model=model, term="alpha (annual)")
            rows.append([f"{panel}: {model}", text(r['sample']), pct(r.paper), pct(r.ours)])
        self.table(["CMS comparison", "Sample", "Paper alpha", "CRSP alpha"], rows,
                   [.28, .30, .21, .21])
        self.p("Full-sample Panel A alphas differ materially; the post-1963 Panel B "
               "comparisons are closer. A gross long/short difference is not the same as "
               "an investable cost-inclusive spread. The result tables distinguish "
               "cost-inclusive CMS from the difference of two net long-only return series.")

        self.heading("8. Trading costs and performance decay")
        subperiods = self.load("critical_tests", "subperiods.csv")
        rows = []
        for period in S.PERIODS:
            r = S.one(subperiods, period=period, portfolio="Conservative", returns="net30")
            rows.append([period, pct(r.compounded), pct(r.excess_vs_market), pct(r.carhart_alpha),
                         interval(r.carhart_ci95_low,r.carhart_ci95_high)])
        self.table(["Period", "Net CAGR", "Excess vs market", "Carhart alpha", "95% alpha interval"], rows,
                   [.19, .17, .21, .18, .25], "Flat 30 bps per dollar traded. Excess and alpha "
                   "are annual arithmetic measures, distinct from compound return.")
        self.p(f"Net 30-bps CAGR is {pct(N['rep_cons_net30_compounded'])} over the paper sample. "
               f"The recent alpha break-even cost is {N['be_alpha|1990–2024']:.0f} bps per dollar "
               f"traded. For 2017-2024, gross excess return and alpha are already nonpositive, "
               "so no positive trading-cost threshold restores them. High early-period "
               "break-even estimates do not establish that historical trading was cheap.")
        self.figure("critical_tests", "fig_rolling.png", "Rolling 120-month excess return "
                    "and Carhart alpha; gross and net series use the same holdings. "
                    "Window estimates are descriptive and strongly overlapping.", height=265)
        self.p("The headline recent net alpha interval includes zero. This is evidence "
               "against a strong claim of persistent recent outperformance, not proof "
               "that the expected alpha is exactly zero. The short post-paper sample "
               "also leaves substantial estimation uncertainty.", "small")

        self.heading("9. Industry-neutral factor diagnostics")
        self.p("Diagnostics use the monthly history-first universe. Low volatility is "
               "oriented favorably as negative volatility. Each signal is demeaned within "
               "industry, divided by the cross-sectional standard deviation of demeaned "
               "values, and clipped to [-3, 3]. Groups with fewer than five members join "
               "Other. The diagnostic composite is the mean of the three complete "
               "neutralized exposures; it differs from the paper's rank-and-screen rule.")
        self.p("Forward total returns retain the formation cohort and terminal events. "
               "Industry adjustment subtracts the equal-weight return of the same "
               "formation industry cohort. Diagnostic cash after an exit earns zero, "
               "a disclosed convention distinct from RF cash in the traded baseline. "
               "IC is the cross-sectional Spearman correlation with forward "
               "industry-adjusted returns.")
        ic = self.load("diagnostics", "ic.csv")
        labels = {"lowvol_z":"Low volatility","momentum_z":"Momentum","npy_z":"Net payout","composite_z":"Composite"}
        self.table(["One-month exposure", "Mean IC", "IC variance", "Mean/SD", "NW t"], [
            [labels[r.exposure], number(r.mean,4), number(r.variance,4),
             number(r.mean_over_sd_literal), number(r.t_nw)]
            for r in ic.loc[ic.h.eq(1)].itertuples()], [.31,.17,.18,.17,.17])
        self.figure("diagnostics", "fig_decay.png", "IC decay with holding horizon and "
                    "persistence of the exposures. Overlapping horizons use lag-aware inference.", height=205)
        deciles = self.load("diagnostics", "deciles_subperiods.csv")
        self.table(["Composite D10 minus D1, one month", "Mean adjusted spread", "NW t"], [
            [r['sample'], pct(r.mean_er), number(r.t_nw)] for _,r in deciles.loc[
                deciles.exposure.eq("composite_z") & deciles.h.eq(1) & deciles.decile.eq("D10-D1")].iterrows()],
                   [.48,.32,.20], "The notebook additionally shows moving IC, decile stock hit "
                   "rates, all horizons and literal mean/standard-deviation ratios.")

        self.heading("10. Factor-mimicking portfolios")
        self.p("Weighted least squares includes the three diagnostic signals, log-size "
               "exposure, industry dummies and historical FF3 stock loadings. The "
               "cross-sectional WLS observation weight is the square root of market "
               "capitalization. The regression operator maps security returns to "
               "unit-exposure factor portfolios. The composite targets unit exposure "
               "to each of the three signal factors and zero exposure to the risk controls.")
        controls = self.load("fmp", "risk_controls.csv")
        self.p(f"Stock FF3 betas use up to 36 monthly excess returns ending at formation, "
               f"with at least 24 factor-covered observations and an intercept. All "
               f"{len(controls):,} formation checks use historical returns; the minimum "
               f"factor coverage is {controls.factor_months_used.min()} months. "
               "The final review added these stock-level controls, rather than treating "
               "future realized market factors as contemporaneous security exposures.")
        pm = self.load("fmp", "paper_metrics.csv")
        chosen = pm.loc[pm.weighting.eq("equal") & pm.period.eq("1929–2024")]
        self.table(["Lagged portfolios K", "Annual active mean", "IR", "Monthly turnover", "Gross leverage"], [
            [int(r.K), pct(r.mean_annual), number(r.ir), pct(r.turnover_one_way_monthly),
             number(r.gross_leverage_mean)] for r in chosen.itertuples()], [.22,.23,.16,.22,.17])
        self.figure("fmp", "fig_cum.png", "Lagged composite paper portfolios. Equal and "
                    "exponentially decaying weights test the persistence/turnover tradeoff.", height=245)
        self.box("These are gross diagnostic factor portfolios with signed weights and "
                 "potentially substantial leverage. Cumulative active performance is "
                 "not a funded long-only NAV. Costs and borrow are explicitly modeled "
                 "in the separate trading exercise; the WLS result is not an implementable "
                 "net strategy claim.")

        self.heading("11. Long/short trading and capacity")
        self.p("The simple trading exercise buys the top and sells the bottom composite "
               "decile. Cohorts are added monthly and expire after n months, for "
               "n = 1, 3, 6 or 12. Costs of 0, 5, 10, 20 and 30 bps per dollar traded "
               "and size-dependent monthly borrow costs are compared. Trades, "
               "positions, NAV accounting and long/short contributions are recorded.")
        nx = self.load("longshort", "nxc.csv")
        chosen = nx.loc[nx.convention.eq("monthly re-weighted (JT)") & nx.cost_bps.eq(10) & nx.borrow.eq("with")]
        self.table(["Holding n", "Annual excess over RF", "IR", "Max drawdown", "Market corr."], [
            [int(r.n), pct(r.er_over_rf_annual), number(r.ir), pct(r.max_drawdown), number(r.corr_crsp_vw)]
            for r in chosen.itertuples()], [.14,.29,.14,.25,.18], "Monthly-reweighted alternative, "
                   "1929-2024. Values rounded to -100% indicate extremely deep drawdown, "
                   "not necessarily an exact zero NAV.")
        self.p("The original buy-and-hold cohorts with n at least 3 are ruined in the "
               "early sample, including August 1932 and May 1933. They are retained "
               "and labeled as failed rather than continued with fictitious positive "
               "wealth. Monthly reweighting was introduced after that outcome and "
               "is explicitly a subsequent convention; its severe drawdowns also "
               "limit the economic attractiveness of the extension.")
        selected = S.one(nx, convention="monthly re-weighted (JT)", n=3, cost_bps=10, borrow="with")
        self.table(["n = 3 contribution", "Annual arithmetic amount"], [
            ["Long positions",pct(selected.long_contribution_annual)],
            ["Short positions",pct(selected.short_contribution_annual)],
            ["Borrow cost",pct(selected.borrow_annual)],
            ["Collateral RF",pct(selected.collateral_rf_annual)],
        ], [.65,.35])
        self.sub("Capacity is a screening estimate")
        self.p(f"The n = 3 monthly-reweighted capacity estimate for the 2020s is "
               f"${N['ls_capacity_2020s']/1e9:.2f} billion at the 10% volume assumption. "
               "Holdings and turnover are related to reported monthly dollar volume. "
               "The estimates use a high participation quantile and normalize "
               "historical AUM to December 2024 market size, not CPI-adjusted dollars. "
               "They omit market impact, daily trade timing and actual borrow "
               "availability; they are not executable AUM guarantees.")

        self.heading("12. Linear portfolio optimization")
        self.p("The long-only linear optimizer maximizes a signal-weighted portfolio "
               "subject to full investment, nonnegative weights, a 2% stock cap, "
               "industry bands around universe capitalization weights, and a "
               "two-way turnover budget. The specified objective uses the "
               "industry-neutral composite z score. Transaction costs scale upward "
               "for smaller or more volatile stocks, with base levels of 10 or 30 bps.")
        self.code("Maximize: sum(alpha[i] * w[i]) - sum(c[i] * abs(w[i]-w_prev[i]))\n"
                  "Subject to: sum(w)=1; 0 <= w[i] <= 0.02\n"
                  "             industry lower <= industry weight <= upper\n"
                  "             sum(abs(w-w_prev)) <= turnover budget")
        opt = self.load("optimization", "grid_subperiods.csv")
        chosen = opt.loc[opt.role.eq("spec") & opt.c0_bps.eq(30) & opt.period.eq("1990–2024")
                         & opt.delta.isin(["2%","5%"]) & opt.tau.isin(["20%","40%"])]
        self.table(["Industry band", "Two-way budget", "Net IR", "Carhart alpha", "95% interval"], [
            [r.delta,r.tau,number(r.ir),pct(r.carhart_alpha_annual),
             interval(r.carhart_alpha_ci95_low,r.carhart_alpha_ci95_high)]
            for r in chosen.itertuples()], [.19,.21,.14,.20,.26])
        self.p(f"For these four recent-period examples, "
               f"{text(N['opt_ci_9024_text'])}. They are nominal intervals selected "
               "from a broader parameter grid and are not adjusted for multiple "
               "comparisons. The post-paper grid produces no alpha interval "
               "excluding zero among the 12 specified 30-bps examples. "
               "Positive selected-grid estimates are not independent validation.")
        self.sub("Expected-return sensitivity and units")
        self.p("A separate exploratory objective converts a signal to expected "
               "three-month return using only completed trailing IC estimates: "
               "alpha = IC times annual volatility times sqrt(3/12) times exposure. "
               "The final review corrected the horizon conversion; sqrt(3) would "
               "incorrectly treat an annualized volatility as monthly. The original "
               "z-score objective is unchanged.")
        self.p("When a stock cap makes an industry's lower band infeasible, the "
               "relaxation is recorded. Minimum feasible turnover is determined "
               "separately; any needed budget relaxation is reported rather "
               "than hidden. Capacity, active skew/kurtosis, market correlation, "
               "hit rates and drawdowns are included in the grid result files.")

        self.heading("13. Quadratic mean-variance optimization")
        self.p("The required quadratic extension adds a true portfolio covariance "
               "penalty to expected return and trading cost. The risk model uses "
               "the last 36 monthly total returns ending at formation. It combines "
               "50% sample covariance with 50% diagonal covariance and scales "
               "monthly covariance to three months, assuming no serial correlation.")
        self.code("Maximize: alpha' w - gamma/2 * w' Sigma_3m w\n"
                  "          - sum(c[i] * abs(w[i]-w_prev[i]))\n"
                  "Sigma_3m = 3 * (0.5 * sample_cov + 0.5 * diagonal_cov)\n"
                  "alpha = completed trailing IC * annual vol * sqrt(3/12) * z")
        self.p("Parameters are fixed heuristics: risk aversion gamma = 5 or 20; "
               "2% stock caps; industry bands of +/-5 percentage points; "
               "40% two-way quarterly turnover after initial allocation; "
               "and scaled costs starting at 30 bps. Until enough completed "
               "IC history exists, expected alpha is zero. The same "
               "formation and holding conventions apply as in the baseline.")
        mv = self.load("mean_variance", "summary.csv")
        chosen = mv.loc[mv.period.isin(["1990–2024","2017–2024"])]
        self.table(["Period / gamma", "Net CAGR", "Volatility", "IR", "Carhart alpha [95% CI]"], [
            [f"{text(r.period)} / {r.risk_aversion:g}",pct(r.compounded),pct(r.volatility),number(r.ir),
             f"{pct(r.carhart_alpha)} {interval(r.alpha_ci_low,r.alpha_ci_high)}"]
            for r in chosen.itertuples()], [.23,.17,.17,.12,.31])
        checks = self.load("mean_variance", "solver_checks.csv")
        self.box(f"<b>Solver verification.</b> Clarabel returns Solved for all "
                 f"{int(checks.formations.sum())} formations across the two variants. "
                 f"The maximum independently measured constraint violation is "
                 f"{checks.max_constraint_violation.max():.2e}. There are no "
                 "risk-window lookahead violations and no turnover-budget "
                 "relaxations. Five infeasible industry lower bounds per "
                 "variant are explicitly relaxed and recorded.")
        self.p("An independent dense constrained-optimization test verifies the "
               "quadratic objective. Market correlations remain high, about "
               "0.87-0.89 in the recent sample. The model is long-only and "
               "industry-constrained; lower volatility does not imply market "
               "neutrality. The extension was introduced after seeing baseline "
               "results and does not establish an optimal parameter choice.")

        self.heading("14. Rank buffer and independent validation")
        self.p("The rank-buffer variant retains an existing holding while it "
               "remains among the best 150 ranks in the eligible low-volatility "
               "pool, then fills vacancies with the best available names. "
               "It targets 100 equally weighted holdings quarterly. The "
               "documented success rule asks for at least 25% less turnover "
               "and a positive net-return difference, rather than a higher "
               "gross backtest selected after the result.")
        paired = self.load("rank_buffer", "paired.csv")
        rows = []
        for kind in ["gross","net10","net30"]:
            r = S.one(paired, returns=kind, period="1990–2024")
            rows.append([kind,pct(r.mean_diff_annual),interval(r.ci95_low,r.ci95_high),
                         number(r.t_nw)])
        self.table(["Buffer minus baseline", "Annual paired difference", "95% interval", "NW t"],
                   rows,[.28,.25,.31,.16])
        self.p(f"Quarterly turnover falls from {pct(N['buf_turn_base'],1)} to "
               f"{pct(N['buf_turn_buf'],1)}. The observed net difference can reflect "
               "both a changed gross path and lower trading cost. A small "
               "observed gross difference does not prove that the signal's "
               "economic quality is unchanged. The paired intervals remain "
               "important even when the mechanical success criterion passes.")
        independent = self.load("professor_checks", "independent_checks.csv")
        self.sub("Three verification passes")
        self.table(["Pass", "Evidence"], [
            ["Paper and assignment", "Construction order, momentum timing, payout definition, "
             "sector distinction and all required diagnostics/construction exercises."],
            ["Data and accounting", "18 raw/normalized/audit input hashes; duplicates; "
             "splits, dividends, delistings, missing returns and company classes."],
            ["Independent calculations", "38,400 selected names; 1,152 gross/net monthly "
             "returns from a separate dollar-holdings recursion; direct signals, "
             "Carhart/Newey-West and sector reconciliation."],
        ], [.30,.70])
        self.p(f"All {len(independent)} independent accounting checks pass. "
               "The complete scientific test suite passes 139 tests. The "
               "executed notebook runs 16 code cells without errors in "
               "empirical and synthetic modes; a fresh checkout also runs "
               "the empirical report without licensed data. Cache hashes "
               "and producing data/source/package identities are checked "
               "before reuse. This validates the tested implementation; "
               "it does not remove the data and modeling assumptions.","small")

        self.heading("15. Running and submitting the project")
        self.p("<b>Main calculation entry point:</b> <font face='Courier'>research/run_all.py</font>, "
               "invoked as a module from Final. It orchestrates all 12 studies "
               "and writes the aggregate result contract and provenance manifest. "
               "The Jupyter notebook is the primary assignment deliverable.")
        self.table(["File or module", "Role"], [
            ["research/run_all.py", "Runs the full research pipeline or selected studies."],
            ["crsp_pipeline", "Imports or extracts raw data, normalizes the panel, writes audits."],
            ["research/engine.py", "Baseline selection and portfolio accounting."],
            ["build_notebook.py / execute_notebook.py", "Generate and execute the Jupyter report."],
            ["build_report_pdf.py", "Generate this written PDF from verified aggregate results."],
            ["presentation/build_pdf.py", "Generate the separate 18-slide PDF and notes."],
            ["package_submission.py", "Create the private runnable package with code and data."],
        ], [.48,.52])
        self.sub("Complete rebuild with the private inputs")
        self.code("cd Final\n"
                  "python -m pip install -r requirements.txt\n"
                  "python -m crsp_pipeline build\n"
                  "python -m research.run_all\n"
                  "python build_notebook.py\n"
                  "python execute_notebook.py\n"
                  "python build_report_pdf.py\n"
                  "python presentation/build_pdf.py\n"
                  "python -m pytest tests -q\n"
                  "python package_submission.py")
        self.p("The full reviewed research rebuild took approximately 16 minutes "
               "on the tested Windows environment; machine and library versions "
               "affect runtime. Cached notebook, written PDF and slides "
               "generate in seconds from the supplied aggregate results. "
               "Dependencies are recorded in requirements.txt and the "
               "tested-version lock file.")
        self.box("<b>Submission:</b> include the executed notebook, code and data "
                 "required by the assignment. This report and the slide PDF "
                 "are companions. The private ZIP includes the seven raw "
                 "parquet inputs, normalized inputs and worked examples. "
                 "Licensed CRSP rows stay in the authorized course package; "
                 "GitHub contains source and aggregate outputs.")

        self.heading("16. Conclusions, limitations and references")
        self.p("The original formula reproduces the central contrast between "
               "Conservative and Speculative stocks: higher compound return "
               "with lower realized volatility. The net-payout share-count "
               "term materially changes selections and returns relative to "
               "dividend yield alone. Industry attribution shows that "
               "both positioning and stock selection contribute, and "
               "the professor's sector-quota construction is tested explicitly.")
        self.p("The recent sample gives a more cautious conclusion. After "
               "known factors and costs, the baseline's recent Carhart "
               "alpha is not significantly different from zero. "
               "Exploratory optimizers and buffers can change risk and "
               "turnover, but selected results do not establish persistent "
               "outperformance or a superior unseen strategy.")
        self.table(["Limitation", "Implication"], [
            ["Turnover 38.9% versus paper 32%", "An unresolved implementation/definition gap remains."],
            ["Early universe below 1,000", "The 1929-1964 strategy uses all available history-eligible names."],
            ["Share-class and size conventions", "Security capitalization and largest-class selection may differ from the authors' universe."],
            ["Dividend and terminal-return proxies", "Corporate-action timing and imputation introduce model uncertainty."],
            ["Some regression/control mismatches", "Close return/risk replication does not imply all paper tables are matched."],
            ["Short post-paper period and grid selection", "Unadjusted intervals and exploratory choices limit inference."],
            ["Capacity and trading assumptions", "Monthly volume omits impact, trade scheduling and borrow availability."],
        ], [.42,.58])
        self.sub("References")
        self.p('Blitz, D. and van Vliet, P. (2018). <i>The Conservative Formula: Quantitative Investing Made Easy.</i> '
               'The Journal of Portfolio Management 44(7). Supplied working paper: '
               '<link href="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152" color="#087C86">SSRN 3145152</link>.',"small")
        self.p('CRSP. <i>Calculations and Index Methodologies.</i> Official '
               '<link href="https://www.crsp.org/wp-content/uploads/guides/CRSP_Calculations_and_Index_Methodologies.pdf" '
               'color="#087C86">methodology guide</link>. WRDS CRSP legacy and Fama-French web exports '
               'supply the local inputs; receipts and hashes accompany the private data.',"small")
        self.p('Clarabel. <i>Python Getting Started.</i> Official '
               '<link href="https://clarabel.org/stable/python/getting_started_py/" color="#087C86">solver documentation</link>. '
               'The assignment is reproduced in Instructions.md. Methods, deviations and independent checks '
               'are detailed in the notebook, FINAL_REVIEW.md and results/.',"small")
        self.p(f"Result provenance: {len(self.manifest['studies'])} completed studies, "
               f"{len(self.manifest['files'])} files. Data-manifest SHA-256: "
               f"{self.manifest['data_manifest_sha256'][:24]}... "
               f"Results last updated UTC: {self.manifest['updated_utc']}.","small")

    @staticmethod
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CCD8DE"))
        canvas.setLineWidth(.5)
        canvas.line(44, letter[1]-29, letter[0]-44, letter[1]-29)
        canvas.setFont("ReportSans", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(44, letter[1]-23, "Yingni Chang and Yikai Shen | MTH 9897 | Conservative Formula")
        canvas.drawString(44, 23, "CRSP 1929-2024 | Final written report")
        canvas.drawRightString(letter[0]-44, 23, str(doc.page))
        canvas.restoreState()

    def build(self, destination=DESTINATION):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.content()
        doc = SimpleDocTemplate(str(destination), pagesize=letter, rightMargin=44,
                                leftMargin=44, topMargin=43, bottomMargin=42,
                                title="The Conservative Formula: CRSP Final Report",
                                author="Yingni Chang and Yikai Shen", subject="MTH 9897 Project 8")
        doc.build(self.story, onFirstPage=self.footer, onLaterPages=self.footer)
        return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, default=results.RESULTS)
    parser.add_argument("--output", type=Path, default=DESTINATION)
    args = parser.parse_args()
    destination = WrittenReport(args.results).build(args.output)
    print(f"Written report: {destination}")


if __name__ == "__main__":
    main()
