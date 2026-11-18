import { useState } from "react";
import useSWR from "swr";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { RefreshCw, Trash2, Plus, RotateCcw, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { api, fetcher, errMsg, fmtDate } from "../lib/api";
import { PageHeader } from "../components/pia/Layout";
import { Empty } from "../components/pia/Badges";

const INTERVALS = [["15", "15 min"], ["60", "1 hour"], ["360", "6 hours"], ["1440", "24 hours"]];

const AddWatch = ({ onAdded }) => {
  const [eco, setEco] = useState("npm");
  const [name, setName] = useState("");
  const [interval, setIntervalV] = useState("60");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/watchlist", { ecosystem: eco, name: name.trim(), interval_minutes: Number(interval) });
      toast.success(`Now watching ${name}`);
      setName("");
      onAdded();
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} data-testid="watch-add-form" className="pia-card grid gap-3 p-6 md:grid-cols-[140px_1fr_160px_auto]">
      <Select value={eco} onValueChange={setEco}>
        <SelectTrigger data-testid="watch-ecosystem-select" className="bg-[#070B14]"><SelectValue /></SelectTrigger>
        <SelectContent><SelectItem value="pypi">PyPI</SelectItem><SelectItem value="npm">npm</SelectItem></SelectContent>
      </Select>
      <Input data-testid="watch-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="package name" className="bg-[#070B14] font-mono" />
      <Select value={interval} onValueChange={setIntervalV}>
        <SelectTrigger data-testid="watch-interval-select" className="bg-[#070B14]"><SelectValue /></SelectTrigger>
        <SelectContent>{INTERVALS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
      </Select>
      <Button data-testid="watch-add-button" type="submit" disabled={busy || !name.trim()} className="bg-sky-400 text-slate-950 hover:bg-sky-300">
        {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}Watch
      </Button>
    </form>
  );
};

export default function Watchlist() {
  const { data: items, mutate } = useSWR("/watchlist", fetcher, { refreshInterval: 5000 });
  const act = async (fn, msg) => {
    try {
      const { data } = await fn();
      toast.success(msg(data));
      setTimeout(mutate, 1500);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  return (
    <div>
      <PageHeader eyebrow="Watch mode" title="Watchlist">
        PIA polls registry APIs (cached, rate-limited, retried with backoff), deduplicates releases and automatically analyses every new version.
      </PageHeader>
      <AddWatch onAdded={mutate} />
      <div className="mt-6 space-y-3">
        {items?.length === 0 && <Empty title="No packages watched">Add a package above, e.g. npm · ms.</Empty>}
        {items?.map((w) => (
          <div key={w.id} data-testid={`watch-item-${w.id}`} className="pia-card pia-card-hover grid items-center gap-4 p-5 lg:grid-cols-[1fr_auto]">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <Link to={`/history?eco=${w.ecosystem}&name=${encodeURIComponent(w.name)}`} className="font-mono text-base text-slate-100 hover:text-sky-300">
                  <span className="text-slate-500">{w.ecosystem}:</span>{w.name}
                </Link>
                <span className="rounded-full border border-emerald-400/40 bg-emerald-400/10 px-2 py-0.5 text-[10px] text-emerald-300">every {w.interval_minutes} min</span>
                {w.last_error && <span className="text-xs text-red-300">error: {w.last_error}</span>}
              </div>
              <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-slate-500">
                <span>latest <span className="text-slate-300">{w.latest_version || "—"}</span></span>
                <span>{w.known_versions} releases known</span>
                <span>{w.checks || 0} checks · {w.new_releases || 0} new</span>
                <span>last {fmtDate(w.last_checked)}</span>
                <span>next {fmtDate(w.next_check)}</span>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" data-testid={`watch-check-${w.id}`} className="border-[#2E436B] bg-transparent text-slate-200 hover:bg-[#121D33]"
                onClick={() => act(() => api.post(`/watchlist/${encodeURIComponent(w.id)}/check`), () => "Check started")}>
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />Check now
              </Button>
              <Button size="sm" variant="outline" data-testid={`watch-rewind-${w.id}`} title="Demo: forget the newest release so it is rediscovered and analysed" className="border-[#F5EFE6]/40 bg-transparent text-[#F5EFE6] hover:bg-[#F5EFE6]/10"
                onClick={() => act(() => api.post(`/watchlist/${encodeURIComponent(w.id)}/rewind`), (d) => `Rediscovering ${d.rediscovering} — alert will follow`)}>
                <RotateCcw className="mr-1.5 h-3.5 w-3.5" />Demo: replay latest
              </Button>
              <Button size="sm" variant="outline" data-testid={`watch-remove-${w.id}`} className="border-red-400/40 bg-transparent text-red-300 hover:bg-red-400/10"
                onClick={() => act(() => api.delete(`/watchlist/${encodeURIComponent(w.id)}`), () => "Removed")}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
