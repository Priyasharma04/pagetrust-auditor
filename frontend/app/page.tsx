'use client';

import { useEffect, useMemo, useState } from 'react';
import { ClickableTable } from '@/components/ClickableTable';
import { DetailsPanel } from '@/components/DetailsPanel';
import { IssueCard } from '@/components/IssueCard';
import { ScoreGauge } from '@/components/ScoreGauge';
import { AuditJob, AuditReport, exportUrl, getAudit, startAudit } from '@/lib/api';

export default function Home() {
  const [url, setUrl] = useState('');
  const [businessType, setBusinessType] = useState('tire shop');
  const [location, setLocation] = useState('Manila');
  const [job, setJob] = useState<AuditJob | null>(null);
  const [error, setError] = useState('');
  const [priorityFilter, setPriorityFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');

  const report: AuditReport | null = job?.report || null;
  const filteredIssues = useMemo(() => {
    if (!report) return [];
    if (priorityFilter === 'all') return report.issues;
    return report.issues.filter((i) => i.priority === priorityFilter);
  }, [report, priorityFilter]);

  useEffect(() => {
    if (!job?.id || job.status === 'complete' || job.status === 'failed') return;
    const t = setInterval(async () => {
      try {
        const next = await getAudit(job.id);
        setJob(next);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Could not poll audit');
      }
    }, 1600);
    return () => clearInterval(t);
  }, [job]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setJob(null);
    try {
      const started = await startAudit({ url, business_type: businessType, location, run_llm: true });
      setJob(started);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Audit failed to start');
    }
  }

  async function copyPrompt() {
    if (report?.improvement_prompt) await navigator.clipboard.writeText(report.improvement_prompt);
  }

  return (
    <main className="min-h-screen">
      <section className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-6 py-10">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-500">Pre-publish QA for AI-generated local pages</p>
              <h1 className="mt-3 text-4xl font-black tracking-tight text-slate-950 md:text-6xl">PageTrust Auditor</h1>
              <p className="mt-4 max-w-2xl text-slate-600">Crawl a business website, test every clickable action, detect local-business gaps, catch generic AI copy, flag contradictions and unsupported claims, then generate a trust score and improvement prompt.</p>
            </div>
            <div className="rounded-2xl bg-slate-950 px-5 py-4 text-sm text-white shadow-soft">
              <p className="font-semibold">Live audit engine</p>
              <p className="text-slate-300">Crawler · Click testing · Local trust scoring</p>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-8">
        <form onSubmit={onSubmit} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-soft">
          <div className="grid gap-4 lg:grid-cols-[2fr_1fr_1fr]">
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-700">Website URL</span>
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com" required className="w-full rounded-2xl border border-slate-200 px-4 py-3" />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-700">Business type</span>
              <input value={businessType} onChange={(e) => setBusinessType(e.target.value)} placeholder="salon, tire shop, restaurant" className="w-full rounded-2xl border border-slate-200 px-4 py-3" />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-700">Expected location</span>
              <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="city/area" className="w-full rounded-2xl border border-slate-200 px-4 py-3" />
            </label>
          </div>
          <div className="mt-4 flex justify-end">
            <button type="submit" className="rounded-2xl bg-slate-950 px-6 py-3 font-semibold text-white hover:bg-slate-800 disabled:opacity-50" disabled={job?.status === 'queued' || job?.status === 'running'}>
              {job?.status === 'queued' || job?.status === 'running' ? 'Auditing...' : 'Run quality audit'}
            </button>
          </div>
          {error && <p className="mt-4 rounded-2xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        </form>

        {job && !report && (
          <div className="mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-soft">
            <p className="font-semibold">Audit status: {job.status}</p>
            <p className="mt-2 text-sm text-slate-500">The backend is crawling, checking links, extracting details, and scoring issues.</p>
            {job.error && <p className="mt-2 text-sm text-red-600">{job.error}</p>}
          </div>
        )}

        {report && (
          <div className="mt-8 space-y-6">
            <ScoreGauge report={report} />
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
              <div>
                <p className="font-semibold">{report.url}</p>
                <p className="text-sm text-slate-500">Fetched with {String(report.metadata.fetch_method || 'unknown')} · {String(report.metadata.clickables_found || 0)} clickables · {String(report.metadata.text_chars_analyzed || 0)} chars analyzed</p>
              </div>
              <div className="flex gap-2">
                <a href={exportUrl(report.id, 'json')} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium">Export JSON</a>
                <a href={exportUrl(report.id, 'pdf')} className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white">Export PDF</a>
              </div>
            </div>

            <DetailsPanel report={report} />

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="font-semibold">Issues found</h2>
                  <p className="text-sm text-slate-500">Priority is based on publishing risk and local-business conversion impact.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {(['all', 'high', 'medium', 'low'] as const).map((p) => (
                    <button key={p} onClick={() => setPriorityFilter(p)} className={`rounded-xl px-3 py-2 text-sm ${priorityFilter === p ? 'bg-slate-950 text-white' : 'bg-slate-100 text-slate-700'}`}>
                      {p.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                {filteredIssues.map((issue) => <IssueCard key={issue.id} issue={issue} />)}
                {!filteredIssues.length && <p className="text-sm text-slate-500">No issues for this filter.</p>}
              </div>
            </div>

            <ClickableTable items={report.clickable_items} />

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-semibold">Generated improvement prompt</h2>
                  <p className="text-sm text-slate-500">Copy-paste this into an LLM or internal rewriting workflow.</p>
                </div>
                <button onClick={copyPrompt} className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white">Copy prompt</button>
              </div>
              <pre className="mt-4 max-h-[460px] overflow-auto whitespace-pre-wrap rounded-2xl bg-slate-950 p-4 text-sm text-slate-100">{report.improvement_prompt}</pre>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
