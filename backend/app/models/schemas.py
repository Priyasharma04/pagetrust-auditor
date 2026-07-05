from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, HttpUrl


class AuditStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    complete = 'complete'
    failed = 'failed'


class Priority(str, Enum):
    high = 'high'
    medium = 'medium'
    low = 'low'


class AuditRequest(BaseModel):
    url: HttpUrl
    business_type: str = Field(default='', description='e.g. tire shop, salon, restaurant')
    location: str = Field(default='', description='city/area/service location')
    expected_business_name: str = Field(default='')
    run_llm: bool = Field(default=False, description='Use optional LLM contradiction checker when OPENAI_API_KEY is configured')


class ClickableItem(BaseModel):
    kind: str
    label: str
    raw_target: str | None = None
    resolved_target: str | None = None
    status: str = 'unknown'
    status_code: int | None = None
    reason: str | None = None
    priority: Priority | None = None


class BusinessDetails(BaseModel):
    business_name_candidates: list[str] = []
    phones: list[str] = []
    emails: list[str] = []
    addresses: list[str] = []
    hours: list[str] = []
    map_links: list[str] = []
    social_links: list[str] = []
    services_or_products: list[str] = []
    ctas: list[str] = []
    local_terms: list[str] = []


class SeoAudit(BaseModel):
    title: str = ''
    meta_description: str = ''
    h1: list[str] = []
    h2: list[str] = []
    image_count: int = 0
    images_missing_alt: int = 0
    og_tags: dict[str, str] = {}
    has_local_business_schema: bool = False
    schema_types: list[str] = []


class Issue(BaseModel):
    id: str
    priority: Priority
    dimension: str
    issue: str
    evidence: str = ''
    why_it_matters: str = ''
    suggested_fix: str = ''
    source: str = 'rule'


class CrawlResult(BaseModel):
    url: str
    final_url: str | None = None
    status_code: int | None = None
    html: str = ''
    text: str = ''
    title: str = ''
    fetch_method: str = 'unknown'
    fetch_error: str | None = None


class AuditReport(BaseModel):
    id: str
    status: AuditStatus
    url: str
    final_url: str | None = None
    business_type: str = ''
    location: str = ''
    trust_score: int = 0
    grade: str = 'unknown'
    summary: str = ''
    issues: list[Issue] = []
    clickable_items: list[ClickableItem] = []
    business_details: BusinessDetails = BusinessDetails()
    seo: SeoAudit = SeoAudit()
    improvement_prompt: str = ''
    metadata: dict[str, Any] = {}


class AuditJob(BaseModel):
    id: str
    status: AuditStatus
    report: AuditReport | None = None
    error: str | None = None
