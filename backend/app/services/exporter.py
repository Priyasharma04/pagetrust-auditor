from __future__ import annotations

import json
from io import BytesIO
from textwrap import shorten

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.models.schemas import AuditReport


def export_json_bytes(report: AuditReport) -> bytes:
    return json.dumps(report.model_dump(mode='json'), ensure_ascii=False, indent=2).encode('utf-8')


def export_pdf_bytes(report: AuditReport) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    def p(text: str, style='BodyText') -> None:
        safe = (text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        story.append(Paragraph(safe, styles[style]))
        story.append(Spacer(1, 8))

    p('PageTrust Auditor Report', 'Title')
    p(f'URL: {report.url}')
    p(f'Business type: {report.business_type or "Not provided"}')
    p(f'Location: {report.location or "Not provided"}')
    p(f'Trust score: {report.trust_score}/100 ({report.grade})')
    p(report.summary)

    p('Top Issues', 'Heading2')
    for issue in report.issues[:18]:
        p(f'[{issue.priority.upper()}] {issue.dimension}: {issue.issue}', 'Heading3')
        if issue.evidence:
            p(f'Evidence: {shorten(issue.evidence, width=650, placeholder="...")}')
        p(f'Fix: {issue.suggested_fix}')

    p('Improvement Prompt', 'Heading2')
    p(report.improvement_prompt[:4500])

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
