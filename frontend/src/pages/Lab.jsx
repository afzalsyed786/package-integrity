import useSWR from "swr";
import { FlaskConical, Globe, Loader2, Play } from "lucide-react";
import { Button } from "../components/ui/button";
import { fetcher } from "../lib/api";
import { useAnalysisJob } from "../lib/useAnalysisJob";
import { PageHeader } from "../components/pia/Layout";
import { SyntheticPill } from "../components/pia/Badges";
import { JobProgress } from "../components/pia/AnalyzeForm";

const RunButton = ({ body, testId, running, start }) => (
  <Button data-testid={testId} disabled={running} onClick={() => start(body)} className="bg-sky-400 text-slate-950 hover:bg-sky-300">
    {running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}Analyze
  </Button>
);

export default function Lab() {
  const { data } = useSWR("/samples", fetcher);
  const { job, start, running } = useAnalysisJob();
  return (
    <div>
      <PageHeader eyebrow="Live demonstration" title="Demo Lab">
        Three clearly-labelled synthetic tampered samples (inert, fabricated for this demo — not real malware) and real recent releases analysed live from PyPI and npm.
      </PageHeader>
      <div className="pia-card mb-6 p-4"><JobProgress job={job} />{!running && <div className="text-xs text-slate-500">Pick a sample to run the full pipeline end to end.</div>}</div>
      <h2 className="mb-4 flex items-center gap-2 font-display text-2xl font-bold text-white"><FlaskConical className="h-5 w-5 text-fuchsia-300" />Synthetic tampered samples</h2>
      <div className="grid gap-6 lg:grid-cols-3">
        {data?.synthetic.map((s, i) => (
          <div key={s.package} data-testid={`sample-card-${s.package}`} className="pia-card pia-card-hover fade-up flex flex-col p-6" style={{ animationDelay: `${i * 60}ms` }}>
            <SyntheticPill />
            <div className="mt-4 font-mono text-sm text-slate-400">{s.style} style · {s.package}@{s.version}</div>
            <div className="mt-1 font-display text-xl font-bold text-white">{s.title}</div>
            <p className="mt-3 flex-1 text-sm leading-relaxed text-slate-400">{s.description}</p>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {s.techniques.map((t) => <span key={t} className="rounded border border-[#F5EFE6]/25 px-2 py-0.5 font-mono text-[10px] text-[#F5EFE6]/90">{t}</span>)}
            </div>
            <div className="mt-5"><RunButton body={{ ecosystem: "synthetic", name: s.package }} testId={`sample-analyze-${s.package}`} running={running} start={start} /></div>
          </div>
        ))}
      </div>
      <h2 className="mb-4 mt-10 flex items-center gap-2 font-display text-2xl font-bold text-white"><Globe className="h-5 w-5 text-emerald-300" />Real releases</h2>
      <div className="grid gap-6 lg:grid-cols-3">
        {data?.real.map((r) => (
          <div key={r.name} data-testid={`real-card-${r.name}`} className="pia-card pia-card-hover flex flex-col p-6">
            <span className="w-fit rounded-full border border-emerald-400/40 bg-emerald-400/10 px-2.5 py-0.5 font-mono text-[10px] tracking-widest text-emerald-300">REAL · {r.ecosystem.toUpperCase()}</span>
            <div className="mt-4 font-display text-xl font-bold text-white">{r.name}<span className="text-sky-300">@{r.version}</span></div>
            <p className="mt-2 flex-1 text-sm text-slate-400">{r.note}</p>
            <div className="mt-5"><RunButton body={{ ecosystem: r.ecosystem, name: r.name, version: r.version }} testId={`real-analyze-${r.name}`} running={running} start={start} /></div>
          </div>
        ))}
      </div>
    </div>
  );
}
