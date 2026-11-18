import { useState } from "react";
import { Loader2, Play } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Progress } from "../ui/progress";
import { useAnalysisJob } from "../../lib/useAnalysisJob";

export const JobProgress = ({ job }) =>
  job && job.status === "running" ? (
    <div data-testid="analysis-progress" className="mt-5 space-y-2">
      <div className="flex justify-between font-mono text-xs text-slate-400">
        <span>{job.message}</span>
        <span>{job.progress}%</span>
      </div>
      <Progress value={job.progress} className="h-1.5 bg-slate-800" />
    </div>
  ) : null;

export default function AnalyzeForm({ compact = false }) {
  const [eco, setEco] = useState("pypi");
  const [name, setName] = useState("");
  const [version, setVersion] = useState("");
  const { job, start, running } = useAnalysisJob();

  const submit = (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    start({ ecosystem: eco, name: name.trim(), version: version.trim() || null });
  };

  return (
    <form onSubmit={submit} data-testid="analyze-form" className="pia-card p-6">
      <div className={`grid gap-3 ${compact ? "sm:grid-cols-[140px_1fr_140px_auto]" : "md:grid-cols-[160px_1fr_180px_auto]"}`}>
        <Select value={eco} onValueChange={setEco}>
          <SelectTrigger data-testid="analyze-ecosystem-select" className="bg-[#070B14]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="pypi" data-testid="eco-option-pypi">PyPI</SelectItem>
            <SelectItem value="npm" data-testid="eco-option-npm">npm</SelectItem>
          </SelectContent>
        </Select>
        <Input data-testid="analyze-package-input" value={name} onChange={(e) => setName(e.target.value)} placeholder={eco === "npm" ? "package name, e.g. ms" : "package name, e.g. six"} className="bg-[#070B14] font-mono" />
        <Input data-testid="analyze-version-input" value={version} onChange={(e) => setVersion(e.target.value)} placeholder="version (latest)" className="bg-[#070B14] font-mono" />
        <Button data-testid="analyze-submit-button" type="submit" disabled={running || !name.trim()} className="bg-sky-400 font-semibold text-slate-950 hover:bg-sky-300">
          {running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
          {running ? "Analyzing" : "Run analysis"}
        </Button>
      </div>
      <JobProgress job={job} />
    </form>
  );
}
