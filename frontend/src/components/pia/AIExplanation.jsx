import { useState } from "react";
import useSWR from "swr";
import { Sparkles, Loader2, Eye, Lock } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../ui/button";
import { api, fetcher, errMsg, fmtDate } from "../../lib/api";
import { VerdictBadge } from "./Badges";

export default function AIExplanation({ analysis, onUpdated }) {
  const { data: status } = useSWR("/ai/status", fetcher);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const expl = analysis.ai_explanation;

  const loadPreview = async () => setPreview((await api.get(`/analyses/${analysis.id}/explain/preview`)).data);
  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/analyses/${analysis.id}/explain`);
      if (data.status === "ok") toast.success("Explanation generated");
      else toast.message(data.text);
      onUpdated?.();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <div className="pia-card p-6">
        <div className="mb-5 flex flex-wrap items-center gap-3 rounded-lg border border-violet-400/25 bg-violet-400/5 px-4 py-3 text-xs text-violet-200">
          <Sparkles className="h-4 w-4" />
          AI heuristic summary — explains findings only. Final verdict (deterministic):
          <VerdictBadge verdict={analysis.verdict} testId="ai-deterministic-verdict" />
        </div>
        {expl ? (
          <div data-testid="ai-explanation-text">
            <div className="mb-3 font-mono text-[11px] text-slate-500">{expl.provider} · {expl.model} · {expl.status} · {fmtDate(expl.created_at)}</div>
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{expl.text}</div>
            <div className="mt-5 text-[11px] text-slate-500">{expl.disclaimer}</div>
          </div>
        ) : (
          <div data-testid="ai-explanation-empty" className="text-sm text-slate-400">No explanation generated yet for this analysis.</div>
        )}
        <div className="mt-6 flex flex-wrap gap-3">
          <Button data-testid="ai-generate-button" onClick={run} disabled={busy} className="bg-violet-400 text-slate-950 hover:bg-violet-300">
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}Generate explanation
          </Button>
          <Button data-testid="ai-preview-button" variant="outline" onClick={loadPreview} className="border-[#2E436B] bg-transparent text-slate-200 hover:bg-[#121D33]">
            <Eye className="mr-2 h-4 w-4" />Preview data sent
          </Button>
        </div>
        {preview && (
          <pre data-testid="ai-payload-preview" className="scroll-thin mt-5 max-h-96 overflow-auto rounded-lg border border-[#1E2C47] bg-[#070B14] p-4 font-mono text-xs text-slate-300">{JSON.stringify(preview, null, 2)}</pre>
        )}
      </div>
      <div className="pia-card space-y-4 p-6 text-sm">
        <div className="font-display text-lg font-bold text-white">Provider</div>
        <div data-testid="ai-provider-status" className="space-y-2 font-mono text-xs text-slate-400">
          <div>provider: <span className="text-slate-200">{status?.provider}</span></div>
          <div>model: <span className="text-slate-200">{status?.model}</span></div>
          <div>configured: <span className={status?.configured ? "text-emerald-300" : "text-amber-300"}>{status ? String(status.configured) : "…"}</span></div>
        </div>
        <div className="flex gap-2 rounded-lg border border-[#1E2C47] p-3 text-xs leading-relaxed text-slate-400">
          <Lock className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
          Only up to six medium+ findings with redacted snippets (≤600 chars) are sent. Secrets and high-entropy blobs are masked. Packages are never uploaded.
        </div>
        {!status?.configured && <div className="text-xs text-amber-200/80">Set GROQ_API_KEY (or PIA_AI_PROVIDER=openrouter + OPENROUTER_API_KEY) on the backend to enable.</div>}
      </div>
    </div>
  );
}
