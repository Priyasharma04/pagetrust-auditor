from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.models.schemas import AuditReport, AuditStatus


class ReportStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.local_dir = Path(self.settings.local_report_dir)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.supabase_client = None
        if self.settings.storage_backend == 'supabase' and self.settings.supabase_url and self.settings.supabase_service_role_key:
            try:
                from supabase import create_client
                self.supabase_client = create_client(self.settings.supabase_url, self.settings.supabase_service_role_key)
            except Exception:
                self.supabase_client = None

    def save(self, report: AuditReport) -> None:
        data = report.model_dump(mode='json')
        data['updated_at'] = datetime.now(timezone.utc).isoformat()
        self._save_local(data)
        if self.supabase_client:
            self._save_supabase(report, data)

    def load(self, audit_id: str) -> AuditReport | None:
        path = self.local_dir / f'{audit_id}.json'
        if path.exists():
            with path.open('r', encoding='utf-8') as f:
                return AuditReport.model_validate(json.load(f))
        return None

    def _save_local(self, data: dict) -> None:
        path = self.local_dir / f'{data["id"]}.json'
        with path.open('w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_supabase(self, report: AuditReport, data: dict) -> None:
        try:
            row = {
                'id': report.id,
                'status': report.status.value if isinstance(report.status, AuditStatus) else str(report.status),
                'url': report.url,
                'business_type': report.business_type,
                'location': report.location,
                'trust_score': report.trust_score,
                'report': data,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }
            self.supabase_client.table(self.settings.supabase_audit_table).upsert(row).execute()
        except Exception:
            # Local persistence remains the source of truth if Supabase is not configured correctly.
            pass
