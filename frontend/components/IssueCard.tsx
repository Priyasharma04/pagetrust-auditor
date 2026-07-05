import type { Issue } from '@/lib/api';

const priorityClass = {
  high: 'border-red-200 bg-red-50 text-red-700',
  medium: 'border-amber-200 bg-amber-50 text-amber-700',
  low: 'border-slate-200 bg-slate-50 text-slate-700'
};

export function IssueCard({ issue }: { issue: Issue }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full border px-2 py-1 text-xs font-semibold ${priorityClass[issue.priority]}`}>
          {issue.priority.toUpperCase()}
        </span>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{issue.dimension}</span>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-500">{issue.source}</span>
      </div>
      <h3 className="mt-3 text-base font-semibold text-slate-950">{issue.issue}</h3>
      {issue.evidence && <p className="mt-2 text-sm text-slate-600"><span className="font-medium">Evidence:</span> {issue.evidence}</p>}
      <p className="mt-2 text-sm text-slate-600"><span className="font-medium">Why:</span> {issue.why_it_matters}</p>
      <p className="mt-2 text-sm text-slate-700"><span className="font-medium">Fix:</span> {issue.suggested_fix}</p>
    </div>
  );
}
