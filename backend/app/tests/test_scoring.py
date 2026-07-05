from app.models.schemas import Issue, Priority
from app.services.scoring import compute_trust_score


def test_score_penalizes_high_priority():
    issues = [
        Issue(id='1', priority=Priority.high, dimension='Clickable audit', issue='broken cta'),
        Issue(id='2', priority=Priority.medium, dimension='Semantic alignment', issue='generic copy'),
    ]
    score, grade, summary = compute_trust_score(issues)
    assert score < 85
    assert 'high' in summary
