import { Link } from "react-router-dom";
import { VerdictBadge, RiskBar, SyntheticPill } from "./Badges";
import { fmtDate } from "../../lib/api";

export default function AnalysesTable({ rows, testId = "analyses-table" }) {
  return (
    <div className="pia-card overflow-x-auto scroll-thin">
      <table data-testid={testId} className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#1E2C47] text-left text-[11px] uppercase tracking-[0.16em] text-slate-500">
            <th className="px-5 py-3 font-medium">Package</th>
            <th className="px-5 py-3 font-medium">Verdict</th>
            <th className="px-5 py-3 font-medium">Risk</th>
            <th className="px-5 py-3 font-medium">Source</th>
            <th className="px-5 py-3 font-medium">Findings</th>
            <th className="px-5 py-3 font-medium">Analyzed</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => {
            const total = Object.values(a.severity_counts || {}).reduce((x, y) => x + y, 0);
            return (
              <tr key={a.id} className="border-b border-[#1E2C47]/60 transition-colors hover:bg-[#121D33]/60">
                <td className="px-5 py-3">
                  <Link to={`/analyses/${a.id}`} data-testid={`analysis-row-${a.id}`} className="font-mono text-slate-100 hover:text-sky-300">
                    <span className="text-slate-500">{a.ecosystem}:</span>{a.package}@{a.version}
                  </Link>
                  {a.synthetic && <div className="mt-1"><SyntheticPill /></div>}
                </td>
                <td className="px-5 py-3"><VerdictBadge verdict={a.verdict} /></td>
                <td className="px-5 py-3"><RiskBar value={a.risk_score} /></td>
                <td className="px-5 py-3 font-mono text-xs text-slate-400">{a.source?.status || "—"}{a.source?.ref ? ` · ${String(a.source.ref).slice(0, 14)}` : ""}</td>
                <td className="px-5 py-3 font-mono text-xs text-slate-300">{total}</td>
                <td className="px-5 py-3 font-mono text-xs text-slate-500">{fmtDate(a.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
