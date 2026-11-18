import { useMemo, useState, useEffect } from "react";
import { FileCode2, Search } from "lucide-react";
import { Input } from "../ui/input";
import { StatusDot } from "./Badges";
import { STATUS_STYLE, fmtBytes } from "../../lib/api";
import DiffViewer from "./DiffViewer";

const FILTERS = ["all", "package_only", "modified", "expected", "identical", "repo_only"];

export default function FileComparison({ analysis, focusPath }) {
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const files = useMemo(() => {
    const repoOnly = (analysis.repo_only || []).map((p) => ({ id: `repo:${p}`, path: p, status: "repo_only", kind: "", has_detail: false, risk_score: 0 }));
    return [...analysis.files, ...repoOnly].sort((a, b) => b.risk_score - a.risk_score || a.path.localeCompare(b.path));
  }, [analysis]);
  const initial = files.find((f) => f.path === focusPath) || files.find((f) => f.status !== "identical" && f.status !== "repo_only") || files[0];
  const [selected, setSelected] = useState(initial);
  useEffect(() => { if (focusPath) { const f = files.find((x) => x.path === focusPath); if (f) setSelected(f); } }, [focusPath, files]);

  const shown = files.filter((f) => (filter === "all" || f.status === filter) && f.path.toLowerCase().includes(q.toLowerCase()));
  const flagged = analysis.findings.filter((f) => f.file === selected?.path && f.line).map((f) => f.line);
  const count = (s) => (s === "all" ? files.length : files.filter((f) => f.status === s).length);

  return (
    <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
      <div className="pia-card flex max-h-[720px] flex-col">
        <div className="space-y-3 border-b border-[#1E2C47] p-4">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <Input data-testid="file-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter files" className="bg-[#070B14] pl-9 font-mono text-xs" />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {FILTERS.map((s) => (
              <button key={s} type="button" data-testid={`file-filter-${s}`} onClick={() => setFilter(s)}
                className={`rounded-md border px-2 py-1 text-[11px] transition-colors ${filter === s ? "border-sky-400/60 bg-sky-400/10 text-sky-200" : "border-[#1E2C47] text-slate-400 hover:text-slate-200"}`}>
                {s === "all" ? "All" : STATUS_STYLE[s].label} <span className="font-mono opacity-70">{count(s)}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="scroll-thin flex-1 overflow-y-auto">
          {shown.map((f) => (
            <button key={f.id} type="button" data-testid={`file-row-${f.path}`} onClick={() => setSelected(f)}
              className={`flex w-full items-center gap-3 border-b border-[#1E2C47]/50 px-4 py-2.5 text-left transition-colors ${selected?.id === f.id ? "bg-[#121D33]" : "hover:bg-[#0F1829]"}`}>
              <FileCode2 className="h-4 w-4 shrink-0 text-slate-500" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-mono text-xs text-slate-200">{f.path}</div>
                <div className="mt-0.5 flex items-center gap-3"><StatusDot status={f.status} />{f.kind && <span className="font-mono text-[10px] text-slate-500">{f.kind}</span>}</div>
              </div>
              {f.risk_score > 0 && <span className="font-mono text-xs text-orange-300">{f.risk_score}</span>}
            </button>
          ))}
        </div>
      </div>
      <div className="pia-card min-w-0 overflow-hidden">
        {selected && (
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-[#1E2C47] p-4 font-mono text-xs text-slate-400">
            <span data-testid="selected-file-path" className="text-sm text-slate-100">{selected.path}</span>
            <StatusDot status={selected.status} />
            <span>{fmtBytes(selected.size)}</span>
            {selected.pkg_sha256 && <span title={selected.pkg_sha256}>pkg {selected.pkg_sha256.slice(0, 12)}</span>}
            {selected.repo_sha256 && <span title={selected.repo_sha256}>repo {selected.repo_sha256.slice(0, 12)}</span>}
            {selected.normalized && <span className="text-sky-300">identical after normalisation</span>}
          </div>
        )}
        {selected?.expected_reason && (
          <div data-testid="expected-reason" className="border-b border-[#1E2C47] bg-sky-400/5 px-4 py-2 text-xs text-sky-200">Expected difference: {selected.expected_reason}</div>
        )}
        <DiffViewer analysisId={analysis.id} file={selected} flaggedLines={flagged} />
      </div>
    </div>
  );
}
