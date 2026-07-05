from __future__ import annotations

import re

from app.models.schemas import Issue, Priority

CLAIM_PATTERNS = [
    (r'\baward[- ]winning\b', 'Award-winning claim'),
    (r'\b(certified|licensed|insured|accredited)\b', 'Credential/licensing claim'),
    (r'\btrusted by (?:thousands|hundreds|\d+[,+]?)\b', 'Scale/trust claim'),
    (r'\b(?:#\s*1|number one|best in|best of|top-rated|5[- ]star|five[- ]star)\b', 'Ranking/rating claim'),
    (r'\bguaranteed\b', 'Guarantee claim'),
    (r'\bverified\b', 'Verification claim'),
    (r'\btestimonial[s]?\b', 'Testimonials section'),
]

EVIDENCE_HINTS = re.compile(r'\b(certificate|license no|licen[cs]e number|award from|rated on|google reviews|review link|proof|source|permit|registration|dti|sec|documented|verified by)\b', re.I)


def unsupported_claim_issues(text: str) -> list[Issue]:
    lowered = text.lower()
    issues: list[Issue] = []
    has_evidence_hint = bool(EVIDENCE_HINTS.search(text))
    for idx, (pattern, label) in enumerate(CLAIM_PATTERNS):
        matches = re.findall(pattern, lowered, flags=re.I)
        if not matches:
            continue
        # Extract snippets around first hit
        match = re.search(pattern, text, flags=re.I)
        start = max(0, (match.start() if match else 0) - 80)
        end = min(len(text), (match.end() if match else 0) + 120)
        snippet = ' '.join(text[start:end].split())
        priority = Priority.high if label in {'Credential/licensing claim', 'Ranking/rating claim', 'Scale/trust claim'} and not has_evidence_hint else Priority.medium
        issues.append(Issue(
            id=f'unsupported-claim-{idx}',
            priority=priority,
            dimension='Unsupported claims',
            issue=f'{label} may need verification before publishing',
            evidence=snippet[:260],
            why_it_matters='Generated local business pages should not invent awards, ratings, certifications, testimonials, licenses, insurance, or popularity claims. These claims affect customer trust and legal/commercial risk.',
            suggested_fix='Keep the claim only if the creator/business owner has evidence. Otherwise replace it with verified facts like services, location, years in operation, real photos, or owner-approved details.',
            source='claim_checker',
        ))
    return issues
