"""Source-map verification: embedded sources vs repository, missing sources, and unmapped bundle code."""
from ..engine import sourcemap
from ..engine.filetypes import read_text
from .base import Detector


def _norm(t: str) -> str:
    return "\n".join(line.rstrip() for line in t.replace("\r\n", "\n").strip().splitlines())


class SourceMapDetector(Detector):
    id = "source-map"

    def run(self, ctx):
        out = []
        repo_set = set(ctx.repo_map)
        for fc in ctx.files:
            if not fc.path.endswith((".js", ".mjs", ".cjs")) or not fc.text or fc.record.status == "identical":
                continue
            map_rel, smap = sourcemap.find_map_reference(fc.path, fc.text)
            if map_rel and map_rel in ctx.pkg_map:
                mt = read_text(ctx.pkg_map[map_rel], ctx.max_text)
                smap = sourcemap.parse_map(mt) if mt else None
            elif map_rel:
                out.append(self._f("Referenced source map is missing", "low", 0.5, fc, None,
                                   f"Bundle references {map_rel}, which is not shipped", f"sourceMappingURL -> {map_rel}"))
                continue
            if not smap:
                continue
            out += self._check_sources(ctx, fc, smap, map_rel or fc.path, repo_set)
            out += self._check_unmapped(fc, smap)
        return out

    def _check_sources(self, ctx, fc, smap, map_rel, repo_set):
        out, missing = [], []
        contents = smap.get("sourcesContent") or []
        for i, src in enumerate(smap["sources"]):
            if not isinstance(src, str) or sourcemap.is_external_source(src):
                continue
            repo_rel = sourcemap.resolve_source(src, map_rel, smap.get("sourceRoot", ""), repo_set)
            if repo_rel is None:
                missing.append(src)
                continue
            content = contents[i] if i < len(contents) else None
            repo_text = read_text(ctx.repo_map[repo_rel], ctx.max_text)
            if isinstance(content, str) and repo_text is not None and _norm(content) != _norm(repo_text):
                out.append(self._f("Source map content differs from repository", "high", 0.8, fc, None,
                                   f"sourcesContent for '{src}' does not match {repo_rel} at the resolved revision",
                                   f"map: {map_rel}\nsource: {src} -> repo {repo_rel}"))
        if missing and ctx.repo_map:
            out.append(self._f("Source map references sources absent from repository", "medium", 0.6, fc, None,
                               f"{len(missing)} original source(s) cannot be found in the repository", "\n".join(missing[:10])))
        return out

    def _check_unmapped(self, fc, smap):
        try:
            mapped = sourcemap.mapped_lines(smap.get("mappings", ""))
        except ValueError:
            return [self._f("Malformed source map", "medium", 0.5, fc, None, "mappings field is not valid VLQ", "")]
        if not any(mapped):
            return []
        suspicious = []
        for i, line in fc.scoped_lines():
            s = line.strip()
            is_mapped = mapped[i - 1] if i - 1 < len(mapped) else False
            if not is_mapped and len(s) > 20 and not s.startswith(("//", "/*", "*")) and "sourceMappingURL" not in s:
                suspicious.append(i)
        if not suspicious:
            return []
        return [self._f("Unmapped code in bundle", "high", 0.8, fc, suspicious[0],
                        f"{len(suspicious)} line(s) of bundle code have no source-map origin — code that exists in no original source file",
                        fc.snippet(suspicious[0], 2))]

    def _f(self, title, sev, conf, fc, line, reason, evidence):
        return self.finding(title=title, category="sourcemap", severity=sev, confidence=conf, reason=reason, evidence=evidence, file=fc.path, line=line)
