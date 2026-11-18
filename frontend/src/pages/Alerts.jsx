import useSWR, { mutate as globalMutate } from "swr";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { CheckCheck, AlertTriangle, Info, Siren } from "lucide-react";
import { Button } from "../components/ui/button";
import { api, fetcher, fmtDate } from "../lib/api";
import { PageHeader } from "../components/pia/Layout";
import { Empty } from "../components/pia/Badges";

const SEV = {
  critical: { icon: Siren, color: "#EF4444" },
  warning: { icon: AlertTriangle, color: "#F97316" },
  info: { icon: Info, color: "#38BDF8" },
};

export default function Alerts() {
  const { data, mutate } = useSWR("/alerts?limit=200", fetcher, { refreshInterval: 5000 });
  const readAll = async () => { await api.post("/alerts/read-all"); toast.success("All alerts marked read"); mutate(); globalMutate("/stats"); };
  const read = async (id) => { await api.post(`/alerts/${id}/read`); mutate(); globalMutate("/stats"); };
  return (
    <div>
      <PageHeader eyebrow="Watch mode output" title="Alerts" actions={
        <Button data-testid="alerts-read-all-button" variant="outline" onClick={readAll} className="border-[#2E436B] bg-transparent text-slate-200 hover:bg-[#121D33]">
          <CheckCheck className="mr-2 h-4 w-4" />Mark all read
        </Button>
      }>New releases and verdicts raised automatically by watch mode.</PageHeader>
      {data?.length === 0 && <Empty title="No alerts">Alerts appear when watched packages publish new releases.</Empty>}
      <div className="space-y-3">
        {data?.map((a, i) => {
          const s = SEV[a.severity] || SEV.info;
          return (
            <div key={a.id} data-testid={`alert-item-${a.id}`} className={`pia-card fade-up flex items-start gap-4 p-5 ${a.read ? "opacity-60" : ""}`} style={{ animationDelay: `${Math.min(i, 10) * 30}ms`, borderLeft: `3px solid ${s.color}` }}>
              <s.icon className="mt-0.5 h-5 w-5 shrink-0" style={{ color: s.color }} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-display text-base font-bold text-slate-100">{a.title}</span>
                  {!a.read && <span className="eburnean-pill rounded-full px-2 py-0.5 font-mono text-[9px] tracking-widest">NEW</span>}
                </div>
                <div className="mt-1 text-sm text-slate-400">{a.message}</div>
                <div className="mt-2 flex gap-4 font-mono text-[11px] text-slate-500">
                  <span>{fmtDate(a.created_at)}</span>
                  {a.analysis_id && <Link to={`/analyses/${a.analysis_id}`} data-testid={`alert-open-analysis-${a.id}`} className="text-sky-300 hover:text-sky-200">Open analysis →</Link>}
                </div>
              </div>
              {!a.read && <button type="button" data-testid={`alert-read-${a.id}`} onClick={() => read(a.id)} className="text-xs text-slate-500 hover:text-slate-200">Mark read</button>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
