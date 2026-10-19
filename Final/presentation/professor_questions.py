"""Questions for the final presentation slide.

Project authors: Yingni Chang and Yikai Shen.
"""
from research import results, summary as S

TITLE = 'Questions for the professor'


def questions(root=results.RESULTS):
    n = S.numbers(root)
    return [
        ('Turnover', f"How can we reconcile {100*n['rep_turnover']:.1f}% quarterly turnover with the paper's {100*n['paper_turnover']:.0f}%?"),
        ('UK coverage', 'Can we obtain historical country and exchange classifications and observed terminal payments?'),
        ('UK comparison', 'Which national benchmark and UK factor series would you prefer for a common-currency comparison?'),
        ('Cost model', 'Is lagged quote scaling a useful approximation, or should costs vary by traded stock and order size?'),
    ]
