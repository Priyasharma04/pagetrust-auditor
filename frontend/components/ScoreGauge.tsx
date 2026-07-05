import type { AuditReport } from '@/lib/api';

export function ScoreGauge({ report }: { report: AuditReport }) {
  const score = report.trust_score;
  const ring = `conic-gradient(#0f172a ${score * 3.6}deg, #e2e8f0 0deg)`;
  return (
    <div className="rounded-3xl bg-white p-6 shadow-soft">
      <div className="flex items-center gap-5">
        <div className="grid h-28 w-28 place-items-center rounded-full" style={{ background: ring }}>
          <div className="grid h-20 w-20 place-items-center rounded-full bg-white">
            <div className="text-center">
              <div className="text-3xl font-bold">{score}</div>
              <div className="text-xs text-slate-500">/100</div>
            </div>
          </div>
        </div>
        <div>
          <p className="text-sm uppercase tracking-wider text-slate-500">Trust score</p>
          <h2 className="text-2xl font-bold">{report.grade}</h2>
          <p className="mt-2 max-w-xl text-sm text-slate-600">{report.summary}</p>
        </div>
      </div>
    </div>
  );
}
