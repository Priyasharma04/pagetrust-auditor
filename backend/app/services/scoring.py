from __future__ import annotations

from collections import Counter

from app.models.schemas import Issue, Priority

BASE_WEIGHTS = {
    Priority.high: 12,
    Priority.medium: 6,
    Priority.low: 2,
}
DIMENSION_MULTIPLIERS = {
    'Clickable audit': 1.25,
    'Local business essentials': 1.25,
    'Contradictions': 1.25,
    'Unsupported claims': 1.10,
    'Semantic alignment': 1.0,
    'SEO/local search': 0.85,
    'LLM/NLI review': 1.05,
}


def compute_trust_score(issues: list[Issue]) -> tuple[int, str, str]:
    penalty = 0.0
    for issue in issues:
        base = BASE_WEIGHTS.get(issue.priority, 4)
        multiplier = DIMENSION_MULTIPLIERS.get(issue.dimension, 1.0)
        penalty += base * multiplier
    score = max(0, min(100, round(100 - penalty)))
    if score >= 90:
        grade = 'Excellent'
    elif score >= 75:
        grade = 'Good'
    elif score >= 60:
        grade = 'Needs review'
    elif score >= 40:
        grade = 'High risk'
    else:
        grade = 'Do not publish yet'

    counts = Counter(issue.priority for issue in issues)
    summary = f'{grade}: {score}/100 trust score with {counts.get(Priority.high, 0)} high, {counts.get(Priority.medium, 0)} medium, and {counts.get(Priority.low, 0)} low priority issues.'
    return score, grade, summary


def sort_issues(issues: list[Issue]) -> list[Issue]:
    order = {Priority.high: 0, Priority.medium: 1, Priority.low: 2}
    return sorted(issues, key=lambda i: (order.get(i.priority, 9), i.dimension, i.issue))
