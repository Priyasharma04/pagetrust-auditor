from __future__ import annotations

import re

from app.models.schemas import Issue, Priority


def polish_issues(text: str) -> list[Issue]:
    issues: list[Issue] = []
    lowered = text.lower()
    if 'lorem ipsum' in lowered or 'placeholder' in lowered or 'coming soon' in lowered:
        issues.append(Issue(
            id='polish-placeholder-copy',
            priority=Priority.high,
            dimension='Content polish/UI',
            issue='Placeholder copy detected',
            evidence='Detected placeholder/lorem/coming soon wording.',
            why_it_matters='Placeholder copy should not reach a published local business website.',
            suggested_fix='Replace placeholders with verified business details or remove the section until details are available.',
            source='polish_checker',
        ))
    if re.search(r'[!?]{3,}', text):
        issues.append(Issue(
            id='polish-excessive-punctuation',
            priority=Priority.low,
            dimension='Content polish/UI',
            issue='Excessive punctuation detected',
            evidence='Found repeated punctuation like !!! or ???.',
            why_it_matters='Small polish issues can make a generated page feel less professional.',
            suggested_fix='Use clean punctuation and keep calls-to-action professional.',
            source='polish_checker',
        ))
    long_sentences = [s.strip() for s in re.split(r'[.!?]\s+', text) if len(s.split()) > 38]
    if len(long_sentences) >= 3:
        issues.append(Issue(
            id='polish-long-sentences',
            priority=Priority.low,
            dimension='Content polish/UI',
            issue='Several sentences are too long',
            evidence=f'{len(long_sentences)} long sentences detected.',
            why_it_matters='Local business copy should be quick to scan, especially on mobile.',
            suggested_fix='Split long sentences and use short service/location/CTA blocks.',
            source='polish_checker',
        ))
    if re.search(r'\b[A-Z]{12,}\b', text):
        issues.append(Issue(
            id='polish-all-caps',
            priority=Priority.low,
            dimension='Content polish/UI',
            issue='All-caps words detected',
            evidence='Detected unusually long all-caps text.',
            why_it_matters='All-caps blocks can feel noisy and reduce readability.',
            suggested_fix='Use sentence case except for verified brand acronyms.',
            source='polish_checker',
        ))
    return issues
