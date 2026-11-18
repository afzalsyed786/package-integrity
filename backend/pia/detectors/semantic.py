"""Semantic change detection for modified files: new sensitive imports, new import-time behaviour, dependency drift."""
import json
import re

from .base import Detector
from .pyast import PyFacts

SENSITIVE_PY = {"subprocess", "socket", "ctypes", "base64", "zlib", "marshal", "urllib", "requests", "http", "pickle", "codecs", "pty", "telnetlib", "ftplib"}
SENSITIVE_JS = {"child_process", "http", "https", "net", "dns", "dgram", "vm", "tls", "os"}
JS_REQUIRE = re.compile(r"(?:require\s*\(\s*|from\s+|import\s*\(\s*)['\"](?:node:)?([\w@/.-]+)['\"]")


class SemanticChangeDetector(Detector):
    id = "semantic-change"

    def run(self, ctx):
        out = []
        for fc in ctx.files:
            if fc.record.status not in ("modified", "expected") or fc.repo_text is None or not fc.text:
                continue
            if fc.record.kind == "python":
                out += self._python(fc)
            elif fc.record.kind == "javascript":
                out += self._js(fc)
            elif fc.path.endswith("package.json"):
                out += self._package_json(fc)
        return out

    def _python(self, fc):
        new, old = PyFacts(fc.text), PyFacts(fc.repo_text)
        if not (new.ok and old.ok):
            return []
        added = {m.split(".")[0] for m, _ in new.imports} - {m.split(".")[0] for m, _ in old.imports}
        added_rel = {m for m, _ in new.imports if m.startswith("_") or m.startswith(".")} - {m for m, _ in old.imports}
        old_calls = {n for n, node in old.calls if node.lineno in old.module_level_lines()}
        top_lines = new.module_level_lines()
        new_top = sorted({(node.lineno, n) for n, node in new.calls if node.lineno in top_lines and n not in old_calls and fc.in_scope(node.lineno)})
        sensitive = sorted(added & SENSITIVE_PY)
        out = []
        if sensitive or (new_top and fc.is_entry):
            parts = []
            if sensitive:
                parts.append(f"new sensitive imports: {', '.join(sensitive)}")
            if new_top:
                parts.append(f"new import-time calls: {', '.join(n for _, n in new_top[:5])}")
            if added_rel:
                parts.append(f"new internal imports: {', '.join(sorted(added_rel)[:5])}")
            line = new_top[0][0] if new_top else next((ln for m, ln in new.imports if m.split('.')[0] in sensitive), None)
            sev = "medium" if not (sensitive and new_top) else "high"
            out.append(self.finding(title="Suspicious semantic change", category="semantic", severity=sev, confidence=0.65,
                                    reason="Published file behaves differently from source — " + "; ".join(parts),
                                    evidence=fc.snippet(line, 2), file=fc.path, line=line))
        return out

    def _js(self, fc):
        new = set(JS_REQUIRE.findall(fc.text))
        old = set(JS_REQUIRE.findall(fc.repo_text))
        sensitive = sorted((new - old) & SENSITIVE_JS)
        if not sensitive:
            return []
        line = next((i for i, l in fc.scoped_lines() if any(s in l for s in sensitive)), None)
        return [self.finding(title="Suspicious semantic change", category="semantic", severity="medium", confidence=0.65,
                             reason=f"Published file imports modules not used by its source: {', '.join(sensitive)}",
                             evidence=fc.snippet(line), file=fc.path, line=line)]

    def _package_json(self, fc):
        try:
            new, old = json.loads(fc.text), json.loads(fc.repo_text)
        except ValueError:
            return []
        out = []
        for key in ("dependencies", "optionalDependencies"):
            added = sorted(set((new.get(key) or {})) - set((old.get(key) or {})))
            if added:
                out.append(self.finding(title="Dependency added at publish time", category="semantic", severity="medium", confidence=0.6,
                                        reason=f"{key} in the published package.json include {', '.join(added)} which the repository does not declare",
                                        evidence="\n".join(f'"{a}": "{new[key][a]}"' for a in added[:8]), file=fc.path))
        for key in ("main", "bin", "exports"):
            if new.get(key) != old.get(key) and key in new:
                out.append(self.finding(title="Entry point changed at publish time", category="semantic", severity="medium", confidence=0.55,
                                        reason=f"'{key}' differs from the repository package.json", evidence=f"package: {new.get(key)}\nrepository: {old.get(key)}", file=fc.path))
        return out
