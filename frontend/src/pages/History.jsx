import { useSearchParams, Link } from "react-router-dom";
import useSWR from "swr";
import { fetcher, fmtDate } from "../lib/api";
import { PageHeader } from "../components/pia/Layout";
import { VerdictBadge, Empty } from "../components/pia/Badges";
import AnalysesTable from "../components/pia/AnalysesTable";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const STATUS_COLOR = { baseline: "#576B8E", discovered: "#38BDF8", analyzed: "#10B981", failed: "#EF4444" };

const Releases = ({ eco, name }) => {
  const { data } = useSWR(eco && name ? `/releases?ecosystem=${eco}&name=${encodeURIComponent(name)}&limit=300` : null, fetcher, { refreshInterval: 6000 });
  if (!data) return null;
  return (
    <div className="pia-card scroll-thin max-h-[520px] overflow-auto">
      <table data-testid="releases-table" className="w-full text-sm">
        <thead className="sticky top-0 bg-[#0D1424]">
          <tr className="border-b border-[#1E2C47] text-left text-[11px] uppercase tracking-[0.16em] text-slate-500">
            <th className="px-5 py-3 font-medium">Version</th><th className="px-5 py-3 font-medium">Published</th>
            <th className="px-5 py-3 font-medium">Status</th><th className="px-5 py-3 font-medium">Verdict</th>
          </tr>
        </thead>
        <tbody>
          {data.map((r) => (
            <tr key={r.id} data-testid={`release-row-${r.version}`} className="border-b border-[#1E2C47]/60">
              <td className="px-5 py-2.5 font-mono text-slate-200">{r.version}{r.prerelease && <span className="ml-2 text-[10px] text-slate-500">pre</span>}</td>
              <td className="px-5 py-2.5 font-mono text-xs text-slate-500">{fmtDate(r.published_at)}</td>
              <td className="px-5 py-2.5 font-mono text-xs" style={{ color: STATUS_COLOR[r.status] }}>{r.status}</td>
              <td className="px-5 py-2.5">{r.analysis_id ? <Link to={`/analyses/${r.analysis_id}`}><VerdictBadge verdict={r.verdict} /></Link> : <span className="text-xs text-slate-600">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default function History() {
  const [params, setParams] = useSearchParams();
  const { data: watch } = useSWR("/watchlist", fetcher);
  const { data: analyses } = useSWR("/analyses?limit=200", fetcher);
  const key = params.get("eco") && params.get("name") ? `${params.get("eco")}:${params.get("name")}` : watch?.[0]?.id;
  const [eco, ...rest] = (key || "").split(":");
  const name = rest.join(":");
  return (
    <div>
      <PageHeader eyebrow="Timeline" title="Release History">Releases discovered by watch mode, plus every analysis PIA has performed.</PageHeader>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-2xl font-bold text-white">Watched releases</h2>
        {watch?.length > 0 && (
          <Select value={key} onValueChange={(v) => { const [e, ...n] = v.split(":"); setParams({ eco: e, name: n.join(":") }); }}>
            <SelectTrigger data-testid="history-package-select" className="w-72 bg-[#0D1424] font-mono text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>{watch.map((w) => <SelectItem key={w.id} value={w.id}>{w.id}</SelectItem>)}</SelectContent>
          </Select>
        )}
      </div>
      {watch?.length === 0 ? <Empty title="No watched packages">Add packages on the Watchlist page to build a release timeline.</Empty> : <Releases eco={eco} name={name} />}
      <h2 className="mb-4 mt-10 font-display text-2xl font-bold text-white">Analysis history</h2>
      {analyses && <AnalysesTable rows={analyses} testId="history-analyses-table" />}
    </div>
  );
}
