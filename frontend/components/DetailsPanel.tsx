import type { AuditReport } from '@/lib/api';

function Pills({ items }: { items: string[] }) {
  if (!items?.length) return <p className="text-sm text-slate-400">Not detected</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {items.slice(0, 10).map((item, idx) => (
        <span key={`${item}-${idx}`} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{item}</span>
      ))}
    </div>
  );
}

export function DetailsPanel({ report }: { report: AuditReport }) {
  const d = report.business_details;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="font-semibold">Extracted local details</h2>
        <div className="mt-4 space-y-4">
          <div><p className="mb-2 text-xs uppercase text-slate-500">Phones</p><Pills items={d.phones} /></div>
          <div><p className="mb-2 text-xs uppercase text-slate-500">Emails</p><Pills items={d.emails} /></div>
          <div><p className="mb-2 text-xs uppercase text-slate-500">Addresses</p><Pills items={d.addresses} /></div>
          <div><p className="mb-2 text-xs uppercase text-slate-500">Hours</p><Pills items={d.hours} /></div>
          <div><p className="mb-2 text-xs uppercase text-slate-500">Services/products clues</p><Pills items={d.services_or_products} /></div>
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="font-semibold">SEO/local signals</h2>
        <div className="mt-4 space-y-3 text-sm">
          <p><span className="font-medium">Title:</span> {report.seo.title || <span className="text-slate-400">Missing</span>}</p>
          <p><span className="font-medium">Meta:</span> {report.seo.meta_description || <span className="text-slate-400">Missing</span>}</p>
          <p><span className="font-medium">H1 count:</span> {report.seo.h1.length}</p>
          <p><span className="font-medium">Images missing alt:</span> {report.seo.images_missing_alt}/{report.seo.image_count}</p>
          <p><span className="font-medium">LocalBusiness schema:</span> {report.seo.has_local_business_schema ? 'Detected' : 'Not detected'}</p>
          <div><p className="mb-2 text-xs uppercase text-slate-500">Schema types</p><Pills items={report.seo.schema_types} /></div>
        </div>
      </div>
    </div>
  );
}
