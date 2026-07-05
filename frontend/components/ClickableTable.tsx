import type { ClickableItem } from '@/lib/api';

export function ClickableTable({ items }: { items: ClickableItem[] }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 p-4">
        <h2 className="font-semibold">Clickable audit</h2>
        <p className="text-sm text-slate-500">Buttons, links, forms, CTAs, phone/email/WhatsApp actions.</p>
      </div>
      <div className="max-h-[460px] overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Label</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Target</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((item, idx) => (
              <tr key={`${item.kind}-${idx}`}>
                <td className="px-4 py-3 text-slate-500">{item.kind}</td>
                <td className="px-4 py-3 font-medium">{item.label}</td>
                <td className="px-4 py-3">
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-xs">{item.status}{item.status_code ? ` ${item.status_code}` : ''}</span>
                </td>
                <td className="max-w-md truncate px-4 py-3 text-slate-500" title={item.resolved_target || item.raw_target || ''}>
                  {item.resolved_target || item.raw_target || 'missing'}
                </td>
              </tr>
            ))}
            {!items.length && (
              <tr><td className="px-4 py-6 text-slate-500" colSpan={4}>No clickable elements detected.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
