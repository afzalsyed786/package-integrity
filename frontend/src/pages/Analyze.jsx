import { PageHeader } from "../components/pia/Layout";
import AnalyzeForm from "../components/pia/AnalyzeForm";

const STEPS = [
  ["Resolve", "Registry metadata, artifact digest, declared repository"],
  ["Download", "Size-capped HTTPS download, digest verified"],
  ["Extract", "Traversal, symlink, size and file-type checks"],
  ["Locate source", "Tag / gitHead resolution via git ls-remote"],
  ["Compare", "Identical, modified, package-only, expected"],
  ["Detect & score", "14 explainable rules → verdict"],
];

export default function Analyze() {
  return (
    <div>
      <PageHeader eyebrow="Run an integrity check" title="Analyze Package">
        Enter an ecosystem, package and optional version. PIA downloads the exact published artifact and compares it with the source at the matching release tag.
      </PageHeader>
      <AnalyzeForm />
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {STEPS.map(([t, d], i) => (
          <div key={t} className="pia-card fade-up p-6" style={{ animationDelay: `${i * 50}ms` }}>
            <div className="font-mono text-xs text-sky-300/80">0{i + 1}</div>
            <div className="mt-2 font-display text-lg font-bold text-white">{t}</div>
            <div className="mt-1 text-sm text-slate-400">{d}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
