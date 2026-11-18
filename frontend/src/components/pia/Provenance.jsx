import { GitBranch, Package, Archive, Terminal } from "lucide-react";
import { Label, AnomalyPill } from "./Badges";
import { fmtBytes, fmtDate } from "../../lib/api";

const Row = ({ k, v, mono = true, testId }) => (
  <div className="flex justify-between gap-6 border-b border-[#1E2C47]/60 py-2 text-xs">
    <span className="text-slate-500">{k}</span>
    <span data-testid={testId} className={`break-all text-right text-slate-200 ${mono ? "font-mono" : ""}`}>{v ?? "—"}</span>
  </div>
);

const Panel = ({ icon: Icon, title, children }) => (
  <div className="pia-card p-6">
    <div className="mb-4 flex items-center gap-2"><Icon className="h-4 w-4 text-sky-300" /><span className="font-display text-lg font-bold text-white">{title}</span></div>
    {children}
  </div>
);

export default function Provenance({ a }) {
  const s = a.source || {};
  const art = a.artifact || {};
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Panel icon={GitBranch} title="Source repository & tag">
        <Row k="repository" v={s.repo} />
        <Row k="tag status" v={s.status} testId="provenance-tag-status" />
        <Row k="resolved ref" v={s.ref ? `${s.ref} (${s.ref_type})` : null} />
        <Row k="commit" v={s.commit} />
        <Row k="registry commit (gitHead)" v={s.expected_commit} />
        <Row k="tag candidates tried" v={(s.candidates || []).join(", ")} />
        <Row k="closest tags" v={(s.nearby_tags || []).join(", ")} />
        {(s.notes || []).map((n) => <div key={n} className="mt-2 text-xs text-amber-200/80">{n}</div>)}
      </Panel>
      <Panel icon={Package} title="Published artifact">
        <Row k="file" v={art.filename} />
        <Row k="kind" v={art.kind} />
        <Row k="size" v={fmtBytes(art.size)} />
        <Row k="sha256" v={art.sha256} />
        <Row k="registry digest verified" v={art.hash_verified == null ? "not published" : String(art.hash_verified)} testId="provenance-hash-verified" />
        <Row k="published" v={fmtDate(a.published_at)} />
        <Row k="build manifest" v={a.manifest ? `${a.manifest.file} (${a.manifest.entries} entries)` : "none"} />
        <Row k="analysis duration" v={a.duration_ms != null ? `${(a.duration_ms / 1000).toFixed(1)} s` : null} />
      </Panel>
      <Panel icon={Archive} title="Safe extraction report">
        <Row k="archive type" v={a.archive?.archive_type} />
        <Row k="files extracted" v={a.archive?.file_count} />
        <Row k="bytes extracted" v={fmtBytes(a.archive?.total_bytes)} />
        <div className="mt-4"><Label>Rejected entries</Label></div>
        {(a.archive?.rejected || []).length === 0 ? (
          <div className="mt-2 text-xs text-emerald-300">None — no traversal, links or special files.</div>
        ) : (
          a.archive.rejected.map((r, i) => (
            <div key={`${r.kind}:${r.name}`} data-testid={`rejected-entry-${i}`} className="mt-2 rounded-md border border-[#F5EFE6]/25 bg-[#070B14] p-3 font-mono text-xs">
              <div className="flex items-center gap-2"><AnomalyPill>{r.kind.replace(/_/g, " ").toUpperCase()}</AnomalyPill></div>
              <div className="mt-2 text-[#F5EFE6]">{r.name}{r.target ? ` → ${r.target}` : ""}</div>
              <div className="mt-1 text-slate-500">{r.reason}</div>
            </div>
          ))
        )}
      </Panel>
      <Panel icon={Terminal} title="Install-time hooks">
        {(a.install_hooks || []).length === 0 ? (
          <div className="text-xs text-emerald-300">No install-time hooks declared by the package.</div>
        ) : (
          a.install_hooks.map((h) => (
            <div key={`${h.kind}:${h.file}:${h.line}:${h.detail}`} className="mb-2 rounded-md border border-[#1E2C47] bg-[#070B14] p-3 font-mono text-xs">
              <div className="text-orange-300">{h.kind}</div>
              <div className="mt-1 text-slate-300">{h.detail}</div>
              <div className="mt-1 text-slate-500">{h.file}{h.line ? `:${h.line}` : ""}</div>
            </div>
          ))
        )}
        <div className="mt-3 text-[11px] text-slate-500">Hooks are parsed statically and never run.</div>
      </Panel>
    </div>
  );
}
