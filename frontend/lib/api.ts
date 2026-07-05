export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export type Priority = 'high' | 'medium' | 'low';
export type Status = 'queued' | 'running' | 'complete' | 'failed';

export interface Issue {
  id: string;
  priority: Priority;
  dimension: string;
  issue: string;
  evidence: string;
  why_it_matters: string;
  suggested_fix: string;
  source: string;
}

export interface ClickableItem {
  kind: string;
  label: string;
  raw_target?: string | null;
  resolved_target?: string | null;
  status: string;
  status_code?: number | null;
  reason?: string | null;
  priority?: Priority | null;
}

export interface BusinessDetails {
  business_name_candidates: string[];
  phones: string[];
  emails: string[];
  addresses: string[];
  hours: string[];
  map_links: string[];
  social_links: string[];
  services_or_products: string[];
  ctas: string[];
  local_terms: string[];
}

export interface SeoAudit {
  title: string;
  meta_description: string;
  h1: string[];
  h2: string[];
  image_count: number;
  images_missing_alt: number;
  og_tags: Record<string, string>;
  has_local_business_schema: boolean;
  schema_types: string[];
}

export interface AuditReport {
  id: string;
  status: Status;
  url: string;
  final_url?: string | null;
  business_type: string;
  location: string;
  trust_score: number;
  grade: string;
  summary: string;
  issues: Issue[];
  clickable_items: ClickableItem[];
  business_details: BusinessDetails;
  seo: SeoAudit;
  improvement_prompt: string;
  metadata: Record<string, unknown>;
}

export interface AuditJob {
  id: string;
  status: Status;
  report?: AuditReport | null;
  error?: string | null;
}

export async function startAudit(payload: {
  url: string;
  business_type: string;
  location: string;
  expected_business_name?: string;
  run_llm?: boolean;
}): Promise<AuditJob> {
  const res = await fetch(`${API_BASE}/api/audits`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAudit(id: string): Promise<AuditJob> {
  const res = await fetch(`${API_BASE}/api/audits/${id}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function exportUrl(id: string, type: 'json' | 'pdf') {
  return `${API_BASE}/api/audits/${id}/export/${type}`;
}
