import { useState, useEffect } from "react";
import useSWR from "swr";
import { fetcher } from "../lib/api";
import { PageHeader } from "../components/pia/Layout";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Empty } from "../components/pia/Badges";
import { AnalysisBody } from "./AnalysisDetail";

const COPY = {
  files: ["File Comparison", "Side-by-side view of the published package against its repository source, with expected differences explained."],
  findings: ["Anomalies & Evidence", "Every finding carries its rule, severity, confidence, evidence snippet and the reason it was raised."],
  ai: ["AI Explanations", "Optional plain-language triage from an open-weight model. It never changes the deterministic verdict."],
};

export default function Workspace({ tab }) {
  const { data: rows } = useSWR("/analyses?limit=100", fetcher);
  const [id, setId] = useState(null);
  useEffect(() => {
    if (rows?.length && !id) setId((rows.find((r) => r.verdict === "Suspicious") || rows[0]).id);
  }, [rows, id]);
  const [title, desc] = COPY[tab];
  return (
    <div>
      <PageHeader eyebrow="Analysis workspace" title={title} actions={
        rows?.length ? (
          <Select value={id || undefined} onValueChange={setId}>
            <SelectTrigger data-testid="workspace-analysis-select" className="w-full bg-[#0D1424] font-mono text-xs lg:w-96"><SelectValue placeholder="Select analysis" /></SelectTrigger>
            <SelectContent>
              {rows.map((r) => (
                <SelectItem key={r.id} value={r.id} data-testid={`workspace-option-${r.id}`}>
                  {r.verdict.padEnd(12, " ")} {r.ecosystem}:{r.package}@{r.version}{r.synthetic ? " (synthetic)" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null
      }>{desc}</PageHeader>
      {rows && rows.length === 0 && <Empty title="Nothing analysed yet">Run an analysis or open the Demo Lab first.</Empty>}
      {id && <AnalysisBody key={`${id}-${tab}`} id={id} defaultTab={tab} />}
    </div>
  );
}
