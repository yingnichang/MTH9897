"""Questions for the final presentation slide.

Project authors: Yingni Chang and Yikai Shen.
"""
from research import results, summary as S

TITLE = 'Questions for the professor'


def questions(root=results.RESULTS):
    n = S.numbers(root)
    return [
        ('Net payout', 'Is a 12-month dividend yield plus the adjusted share-count term based on a 24-month average the intended definition?'),
        ('Industry positioning', "Should the main result retain the paper's global ranking or use industry adjustment? Is our FF12 quota variant appropriate?"),
        ('Turnover', f"Which convention should we use to reconcile our {100*n['rep_turnover']:.1f}% single-counted quarterly turnover with the paper's {100*n['paper_turnover']:.0f}%?"),
        ('Data cleaning', 'Could we compare our dividend, split-adjustment and delisting treatment with your reference cleaning code or a sample of cleaned data?'),
        ('Recent performance', 'Should we investigate the weaker 2017–2024 performance further or document it as a finding? Which implementation checks should we prioritize?'),
    ]
