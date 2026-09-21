"""Build the standalone 10-page report from extracted notebook results."""

import json
import os
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = ROOT / "tmp" / "pdfs"
FINAL_OUTPUT = ROOT / "output" / "pdf" / "MTH9897_Bond_Relative_Value_Report.pdf"
CANDIDATE_OUTPUT = BUILD_DIR / "MTH9897_Bond_Relative_Value_Report.pdf"
DATA = json.loads((BUILD_DIR / "report_data.json").read_text(encoding="utf-8"))

NAVY = colors.HexColor("#17324D")
TEAL = colors.HexColor("#15808D")
GOLD = colors.HexColor("#D5A021")
RED = colors.HexColor("#B24A3A")
INK = colors.HexColor("#202A33")
MID = colors.HexColor("#5F6D78")
LIGHT = colors.HexColor("#EEF2F4")
PALE = colors.HexColor("#F7F9FA")
LINE = colors.HexColor("#D5DDE2")
WHITE = colors.white

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=29, leading=33, textColor=NAVY, alignment=TA_LEFT, spaceAfter=7))
styles.add(ParagraphStyle(name="CoverSub", parent=styles["Normal"], fontName="Helvetica", fontSize=14, leading=19, textColor=MID, spaceAfter=18))
styles.add(ParagraphStyle(name="CoverAuthor", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=NAVY, spaceAfter=18))
styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=NAVY, spaceBefore=0, spaceAfter=9))
styles.add(ParagraphStyle(name="Subsection", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=TEAL, spaceBefore=7, spaceAfter=5))
styles.add(ParagraphStyle(name="BodyReport", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.4, leading=13.4, textColor=INK, spaceAfter=7))
styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.6, leading=10.0, textColor=MID, spaceAfter=4))
styles.add(ParagraphStyle(name="Callout", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=10.3, leading=14.3, textColor=NAVY, spaceAfter=0))
styles.add(ParagraphStyle(name="CalloutLabel", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=7.4, leading=9, textColor=TEAL, spaceAfter=4))
styles.add(ParagraphStyle(name="TableHead", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=7.3, leading=8.6, textColor=WHITE, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="TableCell", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.3, leading=8.7, textColor=INK, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="TableCellLeft", parent=styles["TableCell"], alignment=TA_LEFT))
styles.add(ParagraphStyle(name="Metric", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=17.5, leading=20, textColor=NAVY, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="MetricLabel", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.2, leading=9.1, textColor=MID, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="Reference", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.2, leading=9.2, textColor=MID, spaceAfter=4))


def paragraph(text, style="BodyReport"):
    return Paragraph(text, styles[style])


def percent(value, digits=2):
    return f"{value:.{digits}%}"


def number(value, digits=2):
    return f"{value:,.{digits}f}"


def money(value):
    return f"${value:,.0f}"


def format_date(value, fmt="%B %d, %Y"):
    return datetime.fromisoformat(value).strftime(fmt)


def styled_table(rows, widths, left_cols=(0,), font_size=7.3, padding=4.5):
    converted = []
    for row_index, row in enumerate(rows):
        converted_row = []
        for col_index, value in enumerate(row):
            if row_index == 0:
                converted_row.append(paragraph(str(value), "TableHead"))
            else:
                parent = styles["TableCellLeft" if col_index in left_cols else "TableCell"]
                style = ParagraphStyle(
                    f"cell_{font_size}_{row_index}_{col_index}",
                    parent=parent,
                    fontSize=font_size,
                    leading=font_size + 1.4,
                )
                converted_row.append(Paragraph(str(value), style))
        converted.append(converted_row)
    table = Table(converted, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
    ]
    for row_index in range(1, len(rows)):
        commands.append(("BACKGROUND", (0, row_index), (-1, row_index), WHITE if row_index % 2 else LIGHT))
    table.setStyle(TableStyle(commands))
    return table


def callout(label, text, accent=TEAL):
    box = Table(
        [[paragraph(label.upper(), "CalloutLabel")], [paragraph(text, "Callout")]],
        colWidths=[7.05 * inch],
    )
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("LINEBEFORE", (0, 0), (0, -1), 5, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
        ("TOPPADDING", (0, 1), (-1, 1), 1),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
    ]))
    return box


def metric_strip(items):
    columns = []
    for value, label, color in items:
        value_style = ParagraphStyle("metric_color", parent=styles["Metric"], textColor=color)
        columns.append(Table(
            [[Paragraph(value, value_style)], [paragraph(label, "MetricLabel")]],
            colWidths=[2.26 * inch],
        ))
    table = Table([columns], colWidths=[2.35 * inch] * len(columns))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return table


def page_decorations(canvas, doc):
    canvas.saveState()
    if doc.page == 1:
        canvas.setFillColor(NAVY)
        canvas.rect(0, 10.54 * inch, 8.5 * inch, 0.46 * inch, stroke=0, fill=1)
        canvas.setFillColor(TEAL)
        canvas.rect(0.62 * inch, 0.55 * inch, 0.08 * inch, 9.45 * inch, stroke=0, fill=1)
    else:
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(0.72 * inch, 10.28 * inch, 7.78 * inch, 10.28 * inch)
        canvas.setFont("Helvetica-Bold", 7.2)
        canvas.setFillColor(NAVY)
        canvas.drawString(0.72 * inch, 10.42 * inch, "CORPORATE BOND RELATIVE VALUE")
        canvas.setStrokeColor(LINE)
        canvas.line(0.72 * inch, 0.55 * inch, 7.78 * inch, 0.55 * inch)
        canvas.setFont("Helvetica", 7.2)
        canvas.setFillColor(MID)
        canvas.drawRightString(7.78 * inch, 0.37 * inch, f"Page {doc.page}")
    canvas.restoreState()


clean = {row["trial"]: row for row in DATA["clean_trials"]}
untouched = {row["trial"]: row for row in DATA["raw_trials"]}
pass1 = clean["Pass 1 - Baseline top 3"]
pass2 = clean["Pass 2 - Concentrated top 2"]
pass3 = clean["Pass 3 - Liquidity-aware top 3"]
raw1 = untouched["Pass 1 - Baseline top 3"]
raw2 = untouched["Pass 2 - Concentrated top 2"]
raw3 = untouched["Pass 3 - Liquidity-aware top 3"]
combined = DATA["combined"]
mark = DATA["excluded_mark"]


def build_report():
    FINAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(CANDIDATE_OUTPUT),
        pagesize=letter,
        rightMargin=0.72 * inch,
        leftMargin=0.72 * inch,
        topMargin=0.82 * inch,
        bottomMargin=0.68 * inch,
        title="MTH9897 Corporate Bond Relative Value Report",
        author="Chloe Chang & Yikai Shen",
        subject="Duration-neutral issuer-curve strategy using WRDS corporate bond data",
    )
    story = []

    story += [
        Spacer(1, 0.48 * inch),
        paragraph("CORPORATE BOND RELATIVE VALUE", "Small"),
        paragraph("A Duration-Neutral Issuer-Curve Strategy", "CoverTitle"),
        paragraph("WRDS enhanced end-of-month bond data | August 2022 to March 2025", "CoverSub"),
        paragraph("Chloe Chang &amp; Yikai Shen", "CoverAuthor"),
        Spacer(1, 0.06 * inch),
        metric_strip([
            (percent(pass2["gross_annualized_return"]), "Gross annualized return", TEAL),
            (percent(pass2["gross_annualized_volatility"]), "Annualized volatility", NAVY),
            (percent(pass2["net_25bps_annualized_return"]), "Annualized return after 25 bp cost", RED),
        ]),
        Spacer(1, 0.36 * inch),
        callout(
            "Final finding",
            "The concentrated top-two portfolio produces the strongest result of the three specifications, but its expected return is too small to overcome turnover costs. In this sample, issuer-curve residuals are useful for ranking relative value; they do not provide evidence of implementable trading alpha.",
        ),
        Spacer(1, 0.44 * inch),
        styled_table([
            ["Sample", "Issuers"],
            ["Aug. 2022 to Mar. 2025", "AAPL, AMZN, BA, CAT, DIS, T"],
        ], [3.56 * inch] * 2, left_cols=(), font_size=7.6),
        Spacer(1, 0.65 * inch),
        paragraph("Data source: WRDS enhanced bond returns, two monthly extract files.", "Small"),
        PageBreak(),
    ]

    summary_rows = [["Portfolio", "Gross ann. return", "Gross vol.", "Gross Sharpe", "Avg. turnover", "Net ann. return (25 bp)"]]
    for label, row in [("1. Baseline top 3", pass1), ("2. Concentrated top 2", pass2), ("3. Liquidity-aware top 3", pass3)]:
        summary_rows.append([
            label,
            percent(row["gross_annualized_return"]),
            percent(row["gross_annualized_volatility"]),
            f"{row['gross_sharpe']:.2f}",
            f"{row['average_turnover']:.2f}",
            percent(row["net_25bps_annualized_return"]),
        ])
    story += [
        paragraph("Executive Summary", "Section"),
        callout("Bottom line", "Pass 2 earns 0.39% gross annualized return with 1.02% volatility and a 0.38 gross Sharpe ratio. After a 25 bp one-way turnover charge, annualized return is -1.98% and Sharpe is -1.96."),
        Spacer(1, 9),
        paragraph("Issuer-specific spread curves are estimated for six large corporate issuers, bonds are ranked by actual spread minus fitted spread, and monthly long-cheap/short-rich portfolios are formed. Each issuer sleeve is scaled to approximately zero net DV01 and then combined with equal issuer weights."),
        paragraph("Results across the three specifications", "Subsection"),
        styled_table(summary_rows, [1.75 * inch, 1.12 * inch, 0.90 * inch, 0.90 * inch, 0.95 * inch, 1.38 * inch], left_cols=(0,), font_size=7.4),
        paragraph("Interpretation of the evidence", "Subsection"),
        paragraph("Concentrating on the two strongest residuals improves the gross result relative to the baseline. Adding liquidity to the ranking does not improve performance in the main sample. More importantly, all three designs become negative under the 25 bp cost assumption, so portfolio selection does not overcome implementation frictions."),
        metric_strip([
            (percent(pass2["gross_total_return"]), "Pass 2 gross total return", TEAL),
            (money(combined["total_pnl_usd"]), "Sum of monthly gross PnL on $1mm", NAVY),
            (f"{int(pass2['months'])}", "Monthly observations", GOLD),
        ]),
        Spacer(1, 7),
        paragraph("The economic conclusion is narrow: the model organizes cross-sectional bond opportunities and produces a mechanically sound rate hedge, but the observed edge is not large enough to support a tradable strategy after plausible costs."),
        PageBreak(),
    ]

    sample_rows = [["Issuer", "Observations", "Bonds", "Median duration", "Duration range", "Median spread"]]
    for row in DATA["sample"]:
        sample_rows.append([
            row["company_symbol"],
            f"{row['observations']:,}",
            str(row["unique_bonds"]),
            number(row["median_duration"]),
            f"{row['duration_min']:.2f} - {row['duration_max']:.2f}",
            f"{row['median_spread_bps']:.1f} bps",
        ])
    story += [
        paragraph("1. Data and Cleaning", "Section"),
        paragraph("The sample uses enhanced end-of-month observations for six large non-financial issuers. Bonds must have at least one year to maturity and approximately $200 million outstanding; defaulted and convertible observations are removed, and the modal security level and rating category are kept within each issuer-month."),
        styled_table(sample_rows, [0.74 * inch, 1.02 * inch, 0.65 * inch, 1.12 * inch, 1.30 * inch, 1.18 * inch], left_cols=(0,), font_size=7.5),
        paragraph("Price-quality rule", "Subsection"),
        paragraph("Before fitting curves or constructing returns, an isolated month-end mark is flagged when it differs by more than 40% from both adjacent monthly prices, the neighboring prices are within 20% of one another, and both date gaps are between 25 and 45 days. The rule identifies one observation."),
        Image(str(BUILD_DIR / "price_quality.png"), width=7.05 * inch, height=2.35 * inch),
        callout("Excluded observation", f"AAPL CUSIP {mark['cusip']} is recorded at {mark['previous_price']:.2f}, {mark['price']:.2f}, and {mark['next_price']:.2f} across January, February, and March 2025. The February mark is removed before both model fitting and return construction. The resulting 59-day January-to-March interval is not treated as a monthly return.", accent=RED),
        PageBreak(),
    ]

    curve_rows = [["Issuer", "Fit months", "Average bonds", "Median weighted R2", "Median RMSE"]]
    for row in DATA["curves"]:
        curve_rows.append([
            row["company_symbol"],
            str(row["fit_months"]),
            f"{row['average_bonds']:.1f}",
            f"{row['median_r2']:.3f}",
            f"{row['median_rmse_bps']:.1f} bps",
        ])
    story += [
        paragraph("2. Return and Curve Model", "Section"),
        paragraph("Return construction", "Subsection"),
        paragraph("Positions are formed at month-end and evaluated with the next observation for the same bond when the date gap is 25 to 45 days. WRDS <b>RET_EOM</b> is the primary total-return measure. If it is unavailable, the fallback combines clean-price return with coupon accrual, using an actual/360 day-count convention."),
        callout("Monthly return fallback", "Price return + annual coupon rate x gap days / 360", accent=GOLD),
        paragraph("Issuer-curve specification", "Subsection"),
        paragraph("For each issuer-month, a transparent three-factor spread model is fit. The regression weights combine TRACE dollar volume and amount outstanding, with both inputs winsorized within issuer-month so a single large bond cannot dominate calibration."),
        callout("Curve equation", "T_Spread = b0 + b1 log(1 + Duration) + b2 Duration + b3 Coupon"),
        paragraph("Fit diagnostics", "Subsection"),
        styled_table(curve_rows, [0.85 * inch, 1.05 * inch, 1.20 * inch, 1.55 * inch, 1.28 * inch], left_cols=(0,), font_size=7.6),
        paragraph("The signal is the residual: observed Treasury spread minus fitted spread. Positive residuals are classified as cheap and negative residuals as rich. Ranking is performed within issuer, which avoids comparing raw spread levels across firms with different credit risk."),
        PageBreak(),
    ]

    story += [
        paragraph("3. Issuer Spread Curves", "Section"),
        paragraph(f"The plots below show the latest common cross-section, {format_date(DATA['analysis_date'])}. Marker size reflects TRACE dollar volume, and the fitted line is generated from the weighted regression."),
        Image(str(BUILD_DIR / "issuer_curves.png"), width=7.05 * inch, height=4.08 * inch),
        paragraph("Reading the cross-sections", "Subsection"),
        paragraph("AAPL and AMZN have the strongest median fit statistics, while BA and T display more unexplained spread dispersion. The model does not assume that every residual is a mispricing. A large residual can also reflect liquidity, issue size, maturity, optionality, or missing security-level information."),
        paragraph("This distinction matters for portfolio construction: the residual is a ranking signal, not a guarantee of convergence. The later outlier review checks whether selected bonds have systematically different liquidity and maturity characteristics.", "Small"),
        PageBreak(),
    ]

    story += [
        paragraph("4. Portfolio Construction", "Section"),
        paragraph("Each issuer is treated as a separate relative-value sleeve. The portfolio buys bonds with the widest positive residuals, shorts bonds with the most negative residuals, and scales the short side until the signed market-value duration contribution is approximately zero. Each sleeve is normalized to one dollar of gross market value and available sleeves are equal-weighted."),
        callout("Duration hedge", "sum(Position x Percentage Price x Duration) = 0"),
        paragraph("Three specifications", "Subsection"),
        styled_table([
            ["Pass", "Selection rule", "Research question"],
            ["1. Baseline top 3", "Three cheapest and three richest; size by residual strength", "Does the direct rich-cheap rule produce a payoff?"],
            ["2. Concentrated top 2", "Two strongest bonds on each side", "Do weaker selected residuals dilute the signal?"],
            ["3. Liquidity-aware top 3", "Three per side; ranking incorporates TRACE dollar volume", "Does implementation quality improve selection?"],
        ], [1.35 * inch, 2.83 * inch, 2.84 * inch], left_cols=(0, 1, 2), font_size=7.5),
        paragraph("Rebalancing and costs", "Subsection"),
        paragraph("Portfolios rebalance monthly when a valid next-month return is available. Turnover is one half of the absolute change in bond market weights. Net returns subtract one-way trading costs of 0, 10, 25, or 50 basis points multiplied by turnover."),
        paragraph("Risk that remains", "Subsection"),
        paragraph("DV01 neutrality removes first-order exposure to a parallel Treasury-rate move. It does not neutralize curve slope and curvature, spread duration, issuer beta, downgrade risk, liquidity risk, financing, or short-borrow constraints. These remaining exposures are important because the measured gross return is small."),
        PageBreak(),
    ]

    result_rows = [["Portfolio", "Gross ann.", "Gross vol.", "Sharpe", "Total return", "Win rate", "Turnover", "Net ann. 25 bp"]]
    for label, row in [("1. Baseline top 3", pass1), ("2. Concentrated top 2", pass2), ("3. Liquidity-aware top 3", pass3)]:
        result_rows.append([
            label,
            percent(row["gross_annualized_return"]),
            percent(row["gross_annualized_volatility"]),
            f"{row['gross_sharpe']:.2f}",
            percent(row["gross_total_return"]),
            percent(row["win_rate"], 1),
            f"{row['average_turnover']:.2f}",
            percent(row["net_25bps_annualized_return"]),
        ])
    issuer_rows = [["Issuer", "Ann. return", "Ann. vol.", "Sharpe", "Total return", "Win rate"]]
    for row in DATA["issuers"]:
        issuer_rows.append([
            row["index"],
            percent(row["annualized_return"]),
            percent(row["annualized_volatility"]),
            f"{row['annualized_sharpe']:.2f}",
            percent(row["total_return"]),
            percent(row["win_rate"], 1),
        ])
    story += [
        paragraph("5. Main Backtest Results", "Section"),
        paragraph("Pass 2 is the strongest specification in the main sample. It earns 0.39% gross annualized return with 1.02% volatility, a 0.38 gross Sharpe ratio, and 1.00% cumulative return over 31 months."),
        Image(str(BUILD_DIR / "main_cumulative.png"), width=7.05 * inch, height=2.85 * inch),
        styled_table(result_rows, [1.55 * inch, 0.77 * inch, 0.75 * inch, 0.59 * inch, 0.82 * inch, 0.69 * inch, 0.70 * inch, 0.94 * inch], left_cols=(0,), font_size=6.8),
        paragraph("Issuer breadth", "Subsection"),
        styled_table(issuer_rows, [0.78 * inch, 1.07 * inch, 1.02 * inch, 0.80 * inch, 1.03 * inch, 0.88 * inch], left_cols=(0,), font_size=7.1, padding=3.6),
        paragraph(f"DIS has the strongest issuer-level result, while AMZN and CAT are negative. The best combined month is {format_date(DATA['best_month']['date'], '%B %Y')} at {percent(DATA['best_month']['return'])}; the worst is {format_date(DATA['worst_month']['date'], '%B %Y')} at {percent(DATA['worst_month']['return'])}.", "Small"),
        callout("Untreated-data comparison", "Before excluding the isolated AAPL mark, gross annualized returns were <b>2.75%</b>, <b>4.48%</b>, and <b>5.99%</b> for Passes 1, 2, and 3. These higher values are shown as a data-quality sensitivity on page 9 and are not used as the final estimates.", accent=GOLD),
        PageBreak(),
    ]

    characteristic_rows = [["Group", "Obs.", "Median abs. residual", "Median dollar volume", "Median amount out.", "Median duration", "Median TMT"]]
    order = {"long cheap": 0, "not selected": 1, "short rich": 2}
    for row in sorted(DATA["characteristics"], key=lambda item: order[item["selection_group"]]):
        characteristic_rows.append([
            row["selection_group"].title(),
            f"{row['observations']:,}",
            f"{row['median_abs_residual_bps']:.1f} bps",
            money(row["median_dollar_volume"]),
            money(row["median_amount_outstanding"]),
            f"{row['median_duration']:.2f}",
            f"{row['median_tmt']:.2f}",
        ])
    story += [
        paragraph("6. Costs and Outlier Review", "Section"),
        Image(str(BUILD_DIR / "cost_sensitivity.png"), width=7.05 * inch, height=2.52 * inch),
        paragraph("Average one-way monthly turnover is 0.82. A 10 bp cost reduces annualized return to -0.57%; at 25 bp it falls to -1.98%. The portfolio is close to zero net DV01 by construction, but accurate hedging cannot compensate for a signal whose gross return is smaller than implementation cost."),
        paragraph("Characteristics of selected bonds", "Subsection"),
        styled_table(characteristic_rows, [1.02 * inch, 0.53 * inch, 1.15 * inch, 1.18 * inch, 1.18 * inch, 0.86 * inch, 0.80 * inch], left_cols=(0,), font_size=6.9),
        paragraph("Long-cheap observations have lower median dollar volume, smaller issue size, and longer duration than non-selected observations. Part of the residual therefore appears to compensate investors for liquidity and long-dated risk rather than represent a pure pricing error."),
        callout("Implementation conclusion", "The strongest gross specification is not economically attractive after plausible costs, and its selected bonds carry characteristics that may make actual execution more difficult than the backtest assumes.", accent=RED),
        PageBreak(),
    ]

    sensitivity_rows = [["Portfolio", "Untouched gross", "Main gross", "Untouched net 25 bp", "Main net 25 bp"]]
    for label, raw_row, main_row in [
        ("1. Baseline top 3", raw1, pass1),
        ("2. Concentrated top 2", raw2, pass2),
        ("3. Liquidity-aware top 3", raw3, pass3),
    ]:
        sensitivity_rows.append([
            label,
            percent(raw_row["gross_annualized_return"]),
            percent(main_row["gross_annualized_return"]),
            percent(raw_row["net_25bps_annualized_return"]),
            percent(main_row["net_25bps_annualized_return"]),
        ])
    story += [
        paragraph("7. Data-Quality Sensitivity", "Section"),
        paragraph("As a diagnostic, the same three portfolios are rerun on the otherwise identical data with the isolated-mark screen disabled. This comparison measures how strongly one month-end input can affect fitted residuals, bond selection, and reported returns."),
        Image(str(BUILD_DIR / "data_sensitivity.png"), width=7.05 * inch, height=2.85 * inch),
        styled_table(sensitivity_rows, [2.04 * inch, 1.20 * inch, 1.10 * inch, 1.37 * inch, 1.24 * inch], left_cols=(0,), font_size=7.4),
        paragraph("Interpretation", "Subsection"),
        paragraph(f"With the February 2025 AAPL {mark['cusip']} mark left in place, gross annualized returns rise to 2.75%, 4.48%, and 5.99%. The same price enters the Apple curve and creates two extreme adjacent return intervals, so the higher numbers are a data-quality sensitivity rather than a second performance estimate."),
        callout("Use in the final assessment", "The main-sample results on page 7 are the performance findings. The untouched results are retained only to show why bond-level validation matters before a relative-value backtest is interpreted.", accent=GOLD),
        PageBreak(),
    ]

    story += [
        paragraph("8. Conclusion", "Section"),
        callout("Final assessment", "The issuer-curve framework produces a coherent relative-value ranking and a well-controlled parallel-rate hedge, but the measured return does not survive plausible transaction costs. The strategy is not profitable in this sample after costs."),
        paragraph("What the analysis supports", "Subsection"),
        paragraph("- The three-factor curve provides an interpretable way to compare bonds from the same issuer across the maturity spectrum.<br/>- Concentrating on the strongest residuals performs better than the baseline and liquidity-aware alternatives in the main sample.<br/>- DV01 scaling removes first-order parallel-rate exposure with negligible residual net DV01.<br/>- Turnover costs and liquidity characteristics are large relative to the observed gross return."),
        paragraph("Limitations and next steps", "Subsection"),
        paragraph("The data do not provide complete call schedules, bid-offer spreads, 144A status, subsidiary mapping, or borrow availability. The isolated-mark rule is an ex-post historical validation procedure. The three portfolio specifications are also compared on the same sample, which introduces selection bias."),
        paragraph("A stronger next test would validate month-end prices against a second source, freeze the portfolio rule on an earlier training period, and evaluate later observations with point-in-time transaction costs, financing, borrow constraints, call information, and key-rate risk controls."),
        paragraph("References", "Subsection"),
        paragraph("Boroditsky, M. MTH9897 Quantitative Investment Framework, class notes for sessions 1-2, 2026.", "Reference"),
        paragraph("Nelson, C. R., and Siegel, A. F. (1987). Parsimonious Modeling of Yield Curves. Journal of Business, 60(4), 473-489.", "Reference"),
        paragraph("Wharton Research Data Services. WRDS Bond Returns documentation: <link href='https://wrds-www.wharton.upenn.edu/pages/get-data/wrds-bond-returns/wrds-bond-returns/' color='#15808D'>wrds-www.wharton.upenn.edu/pages/get-data/wrds-bond-returns/wrds-bond-returns/</link>", "Reference"),
        paragraph("Apple Inc. pricing term sheet for the 4.65% note due 2046, CUSIP 037833 BX7: <link href='https://www.sec.gov/Archives/edgar/data/320193/000119312516509001/d168347dfwp.htm' color='#15808D'>SEC filing</link>.", "Reference"),
    ]

    doc.build(story, onFirstPage=page_decorations, onLaterPages=page_decorations)


def validate_report():
    reader = PdfReader(str(CANDIDATE_OUTPUT))
    texts = [page.extract_text() or "" for page in reader.pages]
    full_text = "\n".join(texts)
    checks = {
        "page count": len(reader.pages) == 10,
        "nonblank pages": all(len(text.strip()) > 400 for text in texts),
        "headline result": "0.39%" in texts[0] and "-1.98%" in texts[0],
        "comparison": all(value in texts[6] for value in ["2.75%", "4.48%", "5.99%"]),
        "no revision language": "revis" not in full_text.lower(),
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise RuntimeError(f"Report validation failed: {', '.join(failures)}")
    print(f"Validated {len(reader.pages)} candidate pages")


if __name__ == "__main__":
    build_report()
    validate_report()
    os.replace(CANDIDATE_OUTPUT, FINAL_OUTPUT)
    print(f"Installed validated report at {FINAL_OUTPUT}")
