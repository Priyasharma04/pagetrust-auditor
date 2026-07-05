from __future__ import annotations

from collections import defaultdict

from app.models.schemas import AuditReport, Priority


def generate_improvement_prompt(report: AuditReport) -> str:
    grouped: dict[str, list[str]] = defaultdict(list)
    for issue in report.issues[:25]:
        grouped[issue.dimension].append(f'- [{issue.priority.upper()}] {issue.issue}: {issue.suggested_fix}')

    details = report.business_details
    known = []
    if details.phones:
        known.append(f'Phone: {", ".join(details.phones[:3])}')
    if details.emails:
        known.append(f'Email: {", ".join(details.emails[:3])}')
    if details.addresses:
        known.append(f'Address candidates: {" | ".join(details.addresses[:3])}')
    if details.hours:
        known.append(f'Hours candidates: {" | ".join(details.hours[:3])}')
    if details.services_or_products:
        known.append(f'Service/product clues: {" | ".join(details.services_or_products[:8])}')

    issue_text = '\n'.join(f'\n{dimension}\n' + '\n'.join(items) for dimension, items in grouped.items())
    known_text = '\n'.join(known) if known else 'No reliable business details were extracted. Ask the creator/business owner for verified details before rewriting.'

    return f"""Rewrite and improve this local business website using only verified ground-truth details.

Business type: {report.business_type or '[confirm business type]'}
Expected location: {report.location or '[confirm location]'}
Audit score: {report.trust_score}/100 ({report.grade})

Known extracted details from current page:
{known_text}

Issues to fix:
{issue_text or '- No major issues found, but still keep the copy specific and verified.'}

Rules for the rewrite:
1. Do not invent awards, testimonials, certifications, licenses, insurance, ratings, prices, guarantees, years of operation, or customer counts.
2. Replace generic AI/corporate words with concrete customer language.
3. Mention real services/products, location, contact method, hours, and how to reach/visit/book/order.
4. Keep the tone local, simple, trustworthy, and business-specific.
5. Make every CTA actionable: call, WhatsApp, directions, book, order, or message.
6. If a detail is missing, write a placeholder like [confirm phone number] instead of fabricating it.
7. Keep SEO metadata specific: title, meta description, H1, and LocalBusiness schema should use verified details only.

Return:
- Revised hero section
- Revised services/products section
- Contact/location section
- SEO title and meta description
- JSON-LD LocalBusiness schema draft with placeholders for unknown fields
""".strip()
