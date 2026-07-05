from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.schemas import AuditReport, AuditRequest, AuditStatus, Issue, Priority
from app.services.claims import unsupported_claim_issues
from app.services.contradictions import llm_contradiction_issues, rule_based_contradiction_issues
from app.services.crawler import extract_clickables, fetch_with_playwright
from app.services.extractor import extract_business_details, extract_seo
from app.services.link_checker import check_clickables, clickable_mismatch_issues
from app.services.interaction_auditor import audit_browser_interactions
from app.services.prompt_generator import generate_improvement_prompt
from app.services.polish import polish_issues
from app.services.report_store import ReportStore
from app.services.scoring import compute_trust_score, sort_issues
from app.services.semantic_alignment import semantic_alignment_issues


async def run_audit(request: AuditRequest, audit_id: str | None = None) -> AuditReport:
    audit_id = audit_id or str(uuid4())
    url = str(request.url)
    crawl = await fetch_with_playwright(url)
    issues: list[Issue] = []

    if crawl.fetch_error and not crawl.html:
        issues.append(Issue(
            id='crawl-fetch-failed',
            priority=Priority.high,
            dimension='Crawler',
            issue='Could not fetch the website',
            evidence=crawl.fetch_error[:400],
            why_it_matters='The pre-publish checker cannot verify content, links, or local details if the page cannot be fetched.',
            suggested_fix='Check that the URL is public, deployed, not blocked by robots/security rules, and accessible from a server environment.',
            source='crawler',
        ))

    base_url = crawl.final_url or url
    raw_clickables = extract_clickables(crawl.html, base_url) if crawl.html else []
    raw_clickables = await audit_browser_interactions(base_url, raw_clickables)
    clickables, clickable_issues = await check_clickables(raw_clickables)
    issues.extend(clickable_issues)
    issues.extend(clickable_mismatch_issues(clickables))

    details, detail_issues = extract_business_details(crawl.html, crawl.text, url,expected_location=request.location)
    issues.extend(detail_issues)

    seo, seo_issues = extract_seo(crawl.html, crawl.text, request.business_type, request.location)
    issues.extend(seo_issues)

    issues.extend(semantic_alignment_issues(crawl.text, request.business_type, request.location))
    issues.extend(rule_based_contradiction_issues(crawl.text, details, request.location))
    issues.extend(unsupported_claim_issues(crawl.text))
    issues.extend(polish_issues(crawl.text))
    if request.run_llm:
        issues.extend(await llm_contradiction_issues(crawl.text, request.business_type, request.location))

    issues = dedupe_issues(sort_issues(issues))
    score, grade, summary = compute_trust_score(issues)

    report = AuditReport(
        id=audit_id,
        status=AuditStatus.complete,
        url=url,
        final_url=crawl.final_url,
        business_type=request.business_type,
        location=request.location,
        trust_score=score,
        grade=grade,
        summary=summary,
        issues=issues,
        clickable_items=clickables,
        business_details=details,
        seo=seo,
        metadata={
            'created_at': datetime.now(timezone.utc).isoformat(),
            'fetch_method': crawl.fetch_method,
            'fetch_status_code': crawl.status_code,
            'fetch_error': crawl.fetch_error,
            'text_chars_analyzed': len(crawl.text or ''),
            'clickables_found': len(clickables),
        },
    )
    report.improvement_prompt = generate_improvement_prompt(report)
    ReportStore().save(report)
    return report


def dedupe_issues(issues: list[Issue]) -> list[Issue]:
    seen = set()
    result = []
    for issue in issues:
        key = (issue.dimension.lower(), issue.issue.lower(), issue.evidence[:80].lower())
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result
