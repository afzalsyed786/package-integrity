import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import useSWR from "swr";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { fetcher, VERDICT_STYLE, STATUS_STYLE } from "../lib/api";
import { VerdictBadge, SyntheticPill, Label } from "../components/pia/Badges";
import FindingsList from "../components/pia/Findings";
import FileComparison from "../components/pia/FileComparison";
import AIExplanation from "../components/pia/AIExplanation";
import Provenance from "../components/pia/Provenance";

const VerdictHero = ({ a }) => {
  const st = VERDICT_STYLE[a.verdict];
  return (
    <div data-testid="verdict-hero" className="pia-card fade-up grid gap-6 p-6 lg:grid-cols-[auto_1fr_auto]" style={{ borderColor: st.border }}>
      <div className="flex items-center gap-6">
        <div className="pulse-ring flex h-24 w-24 flex-col items-center justify-center rounded-full border-2" style={{ color: st.color, borderColor: st.color, background: st.bg }}>
          <span data-testid="risk-score-value" className="font-display text-3xl font-extrabold">{a.risk_score}</span>
          <span className="text-[9px] uppercase tracking-widest">risk</span>
        </div>
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3">
          <VerdictBadge verdict={a.verdict} size="lg" testId="analysis-verdict" />
          {a.synthetic && <SyntheticPill />}
        </div>
        <h1 data-testid="analysis-title" className="mt-3 break-all font-display text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
          <span className="text-slate-500">{a.ecosystem}:</span>{a.package}<span className="text-sky-300">@{a.version}</span>
        </h1>
        <ul data-testid="verdict-reasons" className="mt-3 space-y-1 text-sm text-slate-300">
          {a.verdict_reasons.map((r, i) => <li key={`${i}:${r}`} className="flex gap-2"><span style={{ color: st.color }}>▸</span>{r}</li>)}
        </ul>
        {a.metadata?.synthetic && <div className="mt-3 text-xs text-fuchsia-200/80">{a.metadata.description}</div>}
      </div>
      <div className="grid grid-cols-2 gap-x-8 gap-y-3 self-center font-mono text-xs lg:grid-cols-1">
        {["identical", "modified", "package_only", "expected", "repo_only"].map((k) => (
          <div key={k} className="flex items-center justify-between gap-6">
            <span style={{ color: STATUS_STYLE[k].color }}>{STATUS_STYLE[k].label}</span>
            <span data-testid={`summary-${k}`} className="text-slate-200">{a.summary?.[k] ?? 0}</span>
          </div>
        ))}
        <div className="flex items-center justify-between gap-6"><span className="text-slate-400">Coverage</span><span className="text-slate-200">{Math.round((a.coverage || 0) * 100)}%</span></div>
      </div>
    </div>
  );
};

export const AnalysisBody = ({ id, defaultTab = "findings" }) => {
  const [params] = useSearchParams();
  const { data: a, mutate, error } = useSWR(id ? `/analyses/${id}` : null, fetcher);
  const [tab, setTab] = useState(params.get("tab") || defaultTab);
  const [focus, setFocus] = useState(null);
  if (error) return <div className="text-red-300">Analysis not found.</div>;
  if (!a) return <div className="text-slate-400">Loading analysis…</div>;
  const openFile = (path) => { setFocus(path); setTab("files"); };
  return (
    <div className="space-y-6">
      <VerdictHero a={a} />
      {a.errors?.length > 0 && <div className="pia-card border-amber-400/40 p-4 text-xs text-amber-200">{a.errors.join(" · ")}</div>}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="h-auto flex-wrap bg-[#0D1424] p-1">
          <TabsTrigger value="findings" data-testid="tab-findings">Anomalies ({a.findings.length})</TabsTrigger>
          <TabsTrigger value="files" data-testid="tab-files">File comparison ({a.files.length + (a.repo_only?.length || 0)})</TabsTrigger>
          <TabsTrigger value="ai" data-testid="tab-ai">AI explanation</TabsTrigger>
          <TabsTrigger value="provenance" data-testid="tab-provenance">Provenance</TabsTrigger>
        </TabsList>
        <TabsContent value="findings" className="mt-6"><FindingsList findings={a.findings} onOpenFile={openFile} /></TabsContent>
        <TabsContent value="files" className="mt-6"><FileComparison analysis={a} focusPath={focus} /></TabsContent>
        <TabsContent value="ai" className="mt-6"><AIExplanation analysis={a} onUpdated={mutate} /></TabsContent>
        <TabsContent value="provenance" className="mt-6"><Provenance a={a} /></TabsContent>
      </Tabs>
      <div><Label>Analysis id</Label><div className="mt-1 font-mono text-xs text-slate-500">{a.id} · engine {a.engine_version}</div></div>
    </div>
  );
};

export default function AnalysisDetail() {
  const { id } = useParams();
  return <AnalysisBody key={id} id={id} />;
}
