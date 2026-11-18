import useSWR from "swr";
import { Loader2 } from "lucide-react";
import { fetcher } from "../../lib/api";

const ROW_BG = {
  changed: ["rgba(249,115,22,0.10)", "rgba(249,115,22,0.06)"],
  pkg_only: ["rgba(239,68,68,0.14)", "transparent"],
  repo_only: ["transparent", "rgba(16,185,129,0.10)"],
};

const Cell = ({ n, text, bg, flagged }) => (
  <>
    <td className={`w-12 select-none border-r border-[#1E2C47] px-2 text-right align-top text-slate-600 ${flagged ? "bg-[#F5EFE6]/15 text-[#FDFBF7]" : ""}`}>{n ?? ""}</td>
    <td className="whitespace-pre-wrap break-all px-3 align-top" style={{ background: bg }}>{text}</td>
  </>
);

export default function DiffViewer({ analysisId, file, flaggedLines = [] }) {
  const { data, error, isLoading } = useSWR(file?.has_detail ? `/analyses/${analysisId}/files/${file.id}` : null, fetcher);
  if (!file) return null;
  if (!file.has_detail) {
    return <div data-testid="diff-unavailable" className="p-6 text-sm text-slate-400">No content view stored for this file ({file.status === "identical" ? "bit-for-bit identical to source" : "binary or outside inspection limits"}).</div>;
  }
  if (isLoading) return <div className="flex items-center gap-2 p-6 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Loading diff…</div>;
  if (error) return <div className="p-6 text-sm text-red-300">Failed to load diff.</div>;
  const flagged = new Set(flaggedLines);
  return (
    <div data-testid="diff-viewer" className="scroll-thin max-h-[620px] overflow-auto">
      <table className="w-full table-fixed border-collapse font-mono text-[12px] leading-[1.65]">
        {data.mode === "diff" ? (
          <colgroup><col className="w-12" /><col /><col className="w-px" /><col className="w-12" /><col /></colgroup>
        ) : (
          <colgroup><col className="w-12" /><col /></colgroup>
        )}
        <thead className="sticky top-0 z-10 bg-[#121D33] text-left text-[10px] uppercase tracking-[0.16em] text-slate-400">
          <tr>
            <th colSpan={2} className="truncate border-b border-[#1E2C47] px-3 py-2">Published package · {file.path}</th>
            {data.mode === "diff" && <th colSpan={3} className="truncate border-b border-l border-[#1E2C47] px-3 py-2">Repository source · {file.repo_path}</th>}
          </tr>
        </thead>
        <tbody className="text-slate-300">
          {data.mode === "diff"
            ? data.rows.map((r, i) =>
                r[0] === "skip" ? (
                  <tr key={i}><td colSpan={5} className="bg-[#0A1120] px-3 py-1 text-center text-[11px] text-slate-500">{r[2]}</td></tr>
                ) : (
                  <tr key={i}>
                    <Cell n={r[1]} text={r[2]} bg={(ROW_BG[r[0]] || [])[0]} flagged={flagged.has(r[1])} />
                    <td className="w-px border-l border-[#1E2C47]" />
                    <Cell n={r[3]} text={r[4]} bg={(ROW_BG[r[0]] || [])[1]} />
                  </tr>
                ),
              )
            : data.lines.map((line, i) => (
                <tr key={i}><Cell n={i + 1} text={line} bg={file.status === "package_only" ? "rgba(239,68,68,0.06)" : undefined} flagged={flagged.has(i + 1)} /></tr>
              ))}
        </tbody>
      </table>
      {data.truncated && <div className="p-3 text-xs text-slate-500">Output truncated for display.</div>}
    </div>
  );
}
