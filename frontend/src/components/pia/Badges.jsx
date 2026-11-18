import { ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";
import { VERDICT_STYLE, SEVERITY_STYLE, STATUS_STYLE } from "../../lib/api";

const ICONS = { Clean: ShieldCheck, Suspicious: ShieldAlert, Inconclusive: ShieldQuestion };

export const VerdictBadge = ({ verdict, size = "sm", testId }) => {
  const s = VERDICT_STYLE[verdict] || VERDICT_STYLE.Inconclusive;
  const Icon = ICONS[verdict] || ShieldQuestion;
  const big = size === "lg";
  return (
    <span
      data-testid={testId || "verdict-badge"}
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${big ? "px-4 py-2 text-base" : "px-2.5 py-0.5 text-xs"}`}
      style={{ color: s.color, background: s.bg, borderColor: s.border }}
    >
      <Icon className={big ? "h-5 w-5" : "h-3.5 w-3.5"} />
      {verdict}
    </span>
  );
};

export const SeverityBadge = ({ severity }) => {
  const s = SEVERITY_STYLE[severity] || SEVERITY_STYLE.info;
  return (
    <span className="inline-flex items-center rounded px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider" style={{ color: s.color, background: s.bg }}>
      {severity}
    </span>
  );
};

export const StatusDot = ({ status }) => {
  const s = STATUS_STYLE[status] || STATUS_STYLE.identical;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs" style={{ color: s.color }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.color }} />
      {s.label}
    </span>
  );
};

export const AnomalyPill = ({ children = "ANOMALY DETECTED" }) => (
  <span className="eburnean-pill inline-flex items-center rounded-full px-2.5 py-0.5 font-mono text-[10px] font-semibold tracking-[0.14em]">{children}</span>
);

export const SyntheticPill = () => (
  <span data-testid="synthetic-label" className="inline-flex items-center rounded-full border border-fuchsia-400/40 bg-fuchsia-400/10 px-2.5 py-0.5 font-mono text-[10px] font-semibold tracking-[0.12em] text-fuchsia-200">
    SYNTHETIC · NOT REAL MALWARE
  </span>
);

export const Label = ({ children }) => <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{children}</div>;

export const RiskBar = ({ value }) => {
  const color = value >= 60 ? "#EF4444" : value >= 30 ? "#F97316" : value > 0 ? "#EAB308" : "#10B981";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-800">
        <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${Math.max(value, 3)}%`, background: color }} />
      </div>
      <span className="font-mono text-xs" style={{ color }}>{value}</span>
    </div>
  );
};

export const Empty = ({ title, children, testId }) => (
  <div data-testid={testId || "empty-state"} className="pia-card flex flex-col items-start gap-2 p-8">
    <div className="font-display text-lg font-bold text-slate-200">{title}</div>
    <div className="text-sm text-slate-400">{children}</div>
  </div>
);
