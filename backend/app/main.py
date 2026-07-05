from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.core.config import get_settings
from app.models.schemas import AuditJob, AuditReport, AuditRequest, AuditStatus
from app.services.audit_pipeline import run_audit
from app.services.exporter import export_json_bytes, export_pdf_bytes
from app.services.report_store import ReportStore

settings = get_settings()
app = FastAPI(title='PageTrust Auditor API', version='1.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

JOBS: dict[str, AuditJob] = {}


@app.get('/health')
def health() -> dict:
    return {'status': 'ok', 'service': 'PageTrust Auditor API'}


@app.post('/api/audits', response_model=AuditJob)
def create_audit(request: AuditRequest, background_tasks: BackgroundTasks) -> AuditJob:
    audit_id = str(uuid4())
    job = AuditJob(id=audit_id, status=AuditStatus.queued)
    JOBS[audit_id] = job
    background_tasks.add_task(_run_background_audit, audit_id, request)
    return job


@app.post('/api/audits/sync', response_model=AuditReport)
async def create_audit_sync(request: AuditRequest) -> AuditReport:
    # Useful for tests and small demos. Prefer /api/audits for production UI.
    return await run_audit(request)


@app.get('/api/audits/{audit_id}', response_model=AuditJob)
def get_audit(audit_id: str) -> AuditJob:
    if audit_id in JOBS:
        return JOBS[audit_id]
    report = ReportStore().load(audit_id)
    if report:
        return AuditJob(id=audit_id, status=AuditStatus.complete, report=report)
    raise HTTPException(status_code=404, detail='Audit not found')


@app.get('/api/audits/{audit_id}/export/json')
def export_json(audit_id: str) -> Response:
    report = _load_report_or_404(audit_id)
    return Response(
        content=export_json_bytes(report),
        media_type='application/json',
        headers={'Content-Disposition': f'attachment; filename="pagetrust-{audit_id}.json"'},
    )


@app.get('/api/audits/{audit_id}/export/pdf')
def export_pdf(audit_id: str) -> Response:
    report = _load_report_or_404(audit_id)
    return Response(
        content=export_pdf_bytes(report),
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="pagetrust-{audit_id}.pdf"'},
    )


def _load_report_or_404(audit_id: str) -> AuditReport:
    job = JOBS.get(audit_id)
    if job and job.report:
        return job.report
    report = ReportStore().load(audit_id)
    if report:
        return report
    raise HTTPException(status_code=404, detail='Completed report not found')


def _run_background_audit(audit_id: str, request: AuditRequest) -> None:
    JOBS[audit_id] = AuditJob(id=audit_id, status=AuditStatus.running)
    try:
        report = asyncio.run(run_audit(request, audit_id=audit_id))
        JOBS[audit_id] = AuditJob(id=audit_id, status=AuditStatus.complete, report=report)
    except Exception as exc:  # noqa: BLE001
        JOBS[audit_id] = AuditJob(id=audit_id, status=AuditStatus.failed, error=str(exc))
