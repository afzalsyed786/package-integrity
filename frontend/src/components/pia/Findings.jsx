import { useState } from "react";
import { ChevronDown, FileCode2 } from "lucide-react";
import { SeverityBadge, AnomalyPill } from "./Badges";

export const FindingCard = ({ f, onOpenFile, index = 0 }) => {
  const [open, setOpen] = useState(index < 3);
  const anomaly = f.severity === "critical" || f.severity === "high";
  return (
    <div data-testid={`finding-card-${f.id}`} className="pia-card pia-card-hover fade-up p-5" style={{ animationDelay: `${Math.min(index, 10) * 40}ms` }}>
      <button type="button" data-testid={`finding-toggle-${f.id}`} onClick={() => setOpen(!open)} className="flex w-full items-start gap-4 text-left">
        <div className="flex w-12 shrink-0 flex-col items-center">
          <div className="font-display text-2xl font-extrabold text-white">{f.score}</div>
          <div className="text-[9px] uppercase tracking-widest text-slate-500">score</div>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={f.severity} />
            {anomaly && <AnomalyPill />}
            <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">{f.rule_id} · {f.category}</span>
          </div>
          <div className="mt-2 font-display text-lg font-bold text-slate-100">{f.title}</div>
          <div className="mt-1 text-sm text-slate-400">{f.reason}</div>
        </div>
        <ChevronDown className={`mt-1 h-4 w-4 shrink-0 text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="mt-4 space-y-3 pl-16">
          <div className="flex flex-wrap items-center gap-4 font-mono text-xs text-slate-400">
            {f.file && (
              <button type="button" data-testid={`finding-open-file-${f.id}`} onClick={() => onOpenFile?.(f.file)} className="inline-flex items-center gap-1.5 text-sky-300 hover:text-sky-200">
                <FileCode2 className="h-3.5 w-3.5" />{f.file}{f.line ? `:${f.line}` : ""}
              </button>
            )}
            <span>confidence {(f.confidence * 100).toFixed(0)}%</span>
          </div>
          {f.evidence && (
            <pre data-testid={`finding-evidence-${f.id}`} className="scroll-thin max-h-72 overflow-auto rounded-lg border border-[#F5EFE6]/20 bg-[#070B14] p-4 font-mono text-xs leading-relaxed text-[#F5EFE6]">
              {f.evidence}
            </pre>
          )}
        </div>
      )}
    </div>
  );
};

const LEVELS = ["all", "critical", "high", "medium", "low", "info"];

export default function FindingsList({ findings, onOpenFile }) {
  const [level, setLevel] = useState("all");
  const shown = findings.filter((f) => level === "all" || f.severity === level);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {LEVELS.map((l) => (
          <button key={l} type="button" data-testid={`findings-filter-${l}`} onClick={() => setLevel(l)}
            className={`rounded-full border px-3 py-1 font-mono text-xs capitalize transition-colors ${level === l ? "border-sky-400/60 bg-sky-400/10 text-sky-200" : "border-[#1E2C47] text-slate-400 hover:text-slate-200"}`}>
            {l} {l === "all" ? findings.length : findings.filter((f) => f.severity === l).length}
          </button>
        ))}
      </div>
      {shown.length === 0 ? (
        <div data-testid="findings-empty" className="pia-card p-8 text-sm text-slate-400">No findings at this level. Every file was either identical to source or explained by build structure.</div>
      ) : (
        shown.map((f, i) => <FindingCard key={f.id} f={f} index={i} onOpenFile={onOpenFile} />)
      )}
    </div>
  );
}
