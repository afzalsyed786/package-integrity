"""Analysis orchestrator. Downloads, extracts and compares untrusted content without ever executing it."""
import difflib
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path

from .. import __version__
from ..adapters import AnalysisInputError, build_adapters
from ..config import get_settings
from ..detectors import AnalysisContext, FileContext, default_detectors
from ..services.archive import ArchiveError, SafeArchiveInspector
from ..services.http import HttpClient, HttpError
from ..services.repo_resolver import RepositoryResolver, RepoUnavailable, resolve_against_tags
from .comparison import ComparisonEngine, added_lines, walk_files
from .expected import ExpectedClassifier
from .filetypes import CODE_KINDS, read_text
from .models import new_id
from .scoring import score

BASELINE = {
    "network": re.compile(r"urllib\.request|import requests|\bhttpx\b|http\.client|socket\.|\bfetch\(|https?\.request|require\(['\"](?:node:)?https?['\"]\)|axios"),
    "process": re.compile(r"subprocess|os\.system|child_process"),
    "exec": re.compile(r"\beval\(|\bexec\(|new Function"),
}
DETAIL_BUDGET = 8 * 1024 * 1024
MAX_ROWS = 1500


def verify_hashes(expected: dict, actual: dict) -> bool | None:
    checked = [algo for algo in expected if algo in actual]
    if not checked:
        return None
    return all(expected[a].lower() == actual[a].lower() for a in checked)


def side_by_side(pkg: str, repo: str) -> dict:
    a, b = pkg.splitlines(), repo.splitlines()
    rows = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            n = i2 - i1
            idx = list(range(n)) if n <= 8 else list(range(3)) + [None] + list(range(n - 3, n))
            for k in idx:
                rows.append(["skip", i1 + 4, f"… {n - 6} identical lines …", j1 + 4, ""] if k is None else ["equal", i1 + k + 1, a[i1 + k][:300], j1 + k + 1, b[j1 + k][:300]])
        else:
            for x, y in zip_longest(range(i1, i2), range(j1, j2)):
                kind = "changed" if x is not None and y is not None else ("pkg_only" if x is not None else "repo_only")
                rows.append([kind, x + 1 if x is not None else None, a[x][:300] if x is not None else "",
                             y + 1 if y is not None else None, b[y][:300] if y is not None else ""])
        if len(rows) > MAX_ROWS:
            break
    return {"mode": "diff", "rows": rows[:MAX_ROWS], "truncated": len(rows) > MAX_ROWS}


class Analyzer:
    def __init__(self, settings=None, store=None, http=None):
        self.s = settings or get_settings()
        self.http = http or HttpClient(self.s)
        self.adapters = build_adapters(self.http, self.s)
        self.resolver = RepositoryResolver(self.http, self.s)
        self.inspector = SafeArchiveInspector(self.s.limits)
        self.store = store
        self.detectors = default_detectors()

    def analyze(self, ecosystem: str, name: str, version: str | None = None, progress=None) -> dict:
        p = progress or (lambda *a: None)
        adapter = self.adapters.get((ecosystem or "").lower())
        if adapter is None:
            raise AnalysisInputError(f"unsupported ecosystem {ecosystem!r}; available: {', '.join(self.adapters)}")
        t0 = time.time()
        p("resolve", 5, "Resolving release metadata")
        release = adapter.resolve_release((name or "").strip(), (version or "").strip() or None)
        profile = adapter.profile(release)
        tmp = Path(tempfile.mkdtemp(prefix="pia-"))
        try:
            result, details = self._run(adapter, profile, release, tmp, p)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        result["duration_ms"] = int((time.time() - t0) * 1000)
        if self.store:
            self.store.save_analysis(result, details)
        p("done", 100, "Analysis complete")
        return result

    def _base_result(self, release) -> dict:
        return {"id": new_id(), "created_at": datetime.now(timezone.utc).isoformat(), "engine_version": __version__,
                "ecosystem": release.ecosystem, "package": release.name, "version": release.version, "synthetic": release.synthetic,
                "published_at": release.published_at, "metadata": release.metadata, "repo_urls": release.repo_urls,
                "ai_explanation": None, "errors": [], "notes": []}

    def _failed(self, release, artifact, error) -> tuple[dict, dict]:
        r = self._base_result(release)
        r.update(verdict="Inconclusive", risk_score=0, verdict_reasons=[f"Analysis could not complete: {error}"], findings=[], files=[],
                 artifact=artifact, source={"status": "not_resolved"}, archive={}, summary={}, severity_counts={}, category_counts={},
                 install_hooks=[], repo_only=[], coverage=0.0, errors=[str(error)])
        return r, {}

    def _run(self, adapter, profile, release, tmp, p):
        artifact = {"filename": release.filename, "url": release.artifact_url, "kind": release.artifact_kind,
                    "expected_hashes": release.expected_hashes}
        p("download", 15, f"Downloading {release.filename}")
        try:
            path, dl = adapter.download(release, tmp / "download")
        except HttpError as e:
            return self._failed(release, artifact, e)
        artifact.update(size=dl["size"], sha256=dl["digests"]["sha256"], hash_verified=verify_hashes(release.expected_hashes, dl["digests"]))
        p("extract", 30, "Safely extracting archive (traversal/symlink/size checks)")
        try:
            report = self.inspector.extract(path, tmp / "pkg", release.filename)
        except ArchiveError as e:
            return self._failed(release, artifact, f"archive rejected: {e}")
        pkg_root = profile.package_root(report.root, report.files)
        p("source", 45, "Resolving source repository and release tag")
        source, repo_root = self._source(adapter, release, profile, tmp)
        p("compare", 62, "Comparing package files with repository")
        max_text = self.s.limits.max_text_analysis_bytes
        comp = ComparisonEngine(profile, max_text).compare(pkg_root, repo_root)
        classifier = ExpectedClassifier(profile, release, max_text)
        classifier.classify(comp)
        p("detect", 75, "Running detection rules")
        ctx = self._context(release, source, profile, comp, pkg_root, repo_root, report, artifact, classifier.sourcemap_index(), max_text)
        findings, errors = [], []
        for det in self.detectors:
            try:
                findings += det.run(ctx)
            except Exception as e:  # a single faulty rule must not abort the analysis
                errors.append(f"detector {det.id} failed: {type(e).__name__}: {e}")
        p("score", 90, "Scoring and verdict")
        scored = score(findings, comp.records, source, errors)
        result = self._base_result(release)
        counts = {s: sum(r.status == s for r in comp.records) for s in ("identical", "modified", "package_only", "expected")}
        counts.update(repo_only=len(comp.repo_only), total_package_files=len(comp.records), alignment_prefix=comp.prefix)
        details = self._details(ctx, comp)
        result.update(
            verdict=scored["verdict"], risk_score=scored["risk_score"], verdict_reasons=scored["verdict_reasons"],
            coverage=scored["coverage"], severity_counts=scored["severity_counts"], category_counts=scored["category_counts"],
            findings=[f.to_dict() for f in scored["findings"]], files=[r.to_dict() for r in comp.records],
            repo_only=comp.repo_only[:400], summary=counts, artifact=artifact, source=source.to_dict(),
            archive=report.to_dict(), install_hooks=ctx.hooks, errors=errors,
            manifest={"type": ctx.manifest["type"], "file": ctx.manifest["file"], "entries": len(ctx.manifest["entries"])} if ctx.manifest else None,
        )
        return result, details

    def _source(self, adapter, release, profile, tmp):
        candidates = profile.tag_candidates(release.name, release.version)
        if release.local_source:
            res = resolve_against_tags(release.local_tags or {}, release.version, candidates, release.repo_urls[0] if release.repo_urls else "local",
                                       fallback_ref="working-tree")
            res.local = True
            res.notes.append("Synthetic lab: source snapshot is bundled locally in sample_data/")
            return res, adapter.materialize_source(release, tmp / "repo")
        res = self.resolver.resolve(release.repo_urls, release.version, candidates, release.expected_commit, release.repo_subdir)
        if not res.comparable:
            return res, None
        try:
            return res, self.resolver.fetch(res, tmp / "repo")
        except RepoUnavailable as e:
            res.notes.append(str(e))
            res.status, res.ref = "unreachable", None
            return res, None

    def _context(self, release, source, profile, comp, pkg_root, repo_root, report, artifact, smaps, max_text):
        entries = profile.entry_points(pkg_root)
        hooks = profile.install_hooks(pkg_root)
        hook_targets = {t.lstrip("./") for h in hooks for t in re.findall(r"[\w./-]+\.(?:c|m)?js|[\w./-]+\.py|[\w./-]+\.sh", h.get("command", ""))}
        if any(h["kind"].startswith("setup_cmdclass") for h in hooks):
            hook_targets.add("setup.py")
        files = []
        for rec in comp.records:
            if rec.status == "identical":
                continue
            path = comp.pkg_map[rec.path]
            text = read_text(path, max_text) if rec.kind not in ("bytecode", "native", "binary", "asset") else None
            repo_text = read_text(comp.repo_map[rec.repo_path], max_text) if rec.repo_path else None
            added = added_lines(repo_text, text) if (repo_text is not None and text is not None) else None
            files.append(FileContext(record=rec, abs_path=path, text=text, repo_text=repo_text, added=added,
                                     is_entry=rec.path in entries or rec.kind == "pth", is_hook_target=rec.path in hook_targets))
        return AnalysisContext(
            release=release, source=source, profile=profile, files=files, records=comp.records, pkg_root=pkg_root, repo_root=repo_root,
            pkg_map=comp.pkg_map, repo_map=comp.repo_map, archive_report=report, hooks=hooks,
            repo_hooks=profile.install_hooks(repo_root) if repo_root else [], manifest=profile.build_manifest(pkg_root),
            baseline=self._baseline(repo_root, max_text), sourcemaps=smaps, artifact=artifact, max_text=max_text)

    @staticmethod
    def _baseline(repo_root, max_text) -> dict:
        counts = {k: 0 for k in BASELINE}
        for i, (rel, path) in enumerate(walk_files(repo_root).items()):
            if i > 4000:
                break
            if not rel.endswith((".py", ".js", ".mjs", ".cjs", ".ts")) or "/test" in "/" + rel:
                continue
            text = read_text(path, min(max_text, 512 * 1024))
            for cap, pat in BASELINE.items():
                if text and pat.search(text):
                    counts[cap] += 1
        return counts

    @staticmethod
    def _details(ctx, comp) -> dict:
        details, used = {}, 0
        ordered = sorted(ctx.files, key=lambda f: -f.record.risk_score)
        for fc in ordered:
            if fc.text is None or used > DETAIL_BUDGET:
                continue
            if fc.repo_text is not None:
                payload = side_by_side(fc.text, fc.repo_text)
            else:
                lines = fc.text.splitlines()
                payload = {"mode": "single", "lines": [line[:300] for line in lines[:MAX_ROWS]], "truncated": len(lines) > MAX_ROWS}
            used += sum(len(str(r)) for r in payload.get("rows", payload.get("lines", [])))
            details[fc.record.id] = payload
            fc.record.has_detail = True
        return details


def is_code_kind(kind: str) -> bool:
    return kind in CODE_KINDS
