"""Behavioural code detectors: dynamic execution, process spawning, network access, credential access.

Only lines introduced by the package (package-only files or lines added relative to the repository) are in scope,
and severity is adjusted by context (entry point, install hook, repository baseline)."""
import ast
import re

from ..engine.models import downgrade, upgrade
from .base import Detector
from .pyast import PyFacts

DECODERS = {"base64.b64decode", "base64.b32decode", "base64.b85decode", "base64.a85decode", "base64.decodebytes",
            "base64.urlsafe_b64decode", "binascii.a2b_base64", "binascii.unhexlify", "bytes.fromhex", "zlib.decompress",
            "gzip.decompress", "lzma.decompress", "bz2.decompress", "codecs.decode", "marshal.loads", ".decode", ".decompress"}
PY_EXEC = {"eval", "exec", "compile", "builtins.eval", "builtins.exec", "builtins.compile", "marshal.loads", "pickle.loads",
           "types.FunctionType", "importlib.import_module", "__import__"}
JS_EXEC = re.compile(r"\beval\s*\(|\bnew\s+Function\s*\(|\bvm\.(?:runInThisContext|runInNewContext|runInContext|Script)\b|\bsetTimeout\s*\(\s*['\"`]")
JS_DECODE = re.compile(r"atob\s*\(|Buffer\.from\s*\([^)]*['\"](?:base64|hex)['\"]|fromCharCode|unescape\s*\(")
PY_PROC = ("subprocess.", "os.system", "os.popen", "os.exec", "os.spawn", "os.posix_spawn", "pty.spawn", "ctypes.CDLL", "ctypes.cdll", "ctypes.windll", "os.startfile")
JS_PROC = re.compile(r"require\s*\(\s*['\"](?:node:)?child_process['\"]\s*\)|\b(?:execSync|spawnSync|execFile|execFileSync|spawn|exec)\s*\(\s*['\"`]")
DANGEROUS_CMD = re.compile(r"curl\s|wget\s|bash\s+-c|sh\s+-c|/bin/sh|powershell|/dev/tcp|nc\s+-e|chmod\s+\+x|Invoke-Expression|certutil", re.I)
PY_NET = ("urllib.request.", "urllib.urlopen", "urllib2.", "requests.", "httpx.", "http.client.", "socket.socket", "socket.create_connection",
          "ftplib.", "smtplib.", "aiohttp.", "telnetlib.")
JS_NET = re.compile(r"\bfetch\s*\(|\bhttps?\.(?:request|get)\s*\(|require\s*\(\s*['\"](?:node:)?(?:https?|net|dgram|dns|tls)['\"]\s*\)|XMLHttpRequest|\baxios\.|new\s+WebSocket")
URL_OR_IP = re.compile(r"https?://[^\s'\"<>)]+|\b(?:\d{1,3}\.){3}\d{1,3}\b")
ENV_BULK = re.compile(r"dict\(\s*os\.environ\s*\)|os\.environ\.copy\(\)|json\.dumps\(\s*(?:dict\()?os\.environ|JSON\.stringify\(\s*process\.env\s*\)|Object\.(?:keys|entries)\(\s*process\.env\s*\)")
ENV_SECRET = re.compile(r"(?:os\.environ|os\.getenv|process\.env)[\[\.(\s'\"]*([A-Z0-9_]*(?:TOKEN|SECRET|PASSW|API_?KEY|AWS_|NPM_|GITHUB|PRIVATE|CREDENTIAL)[A-Z0-9_]*)")
SECRET_FILES = re.compile(r"\.ssh/|id_rsa|id_ed25519|\.aws/credentials|\.npmrc|\.pypirc|\.git-credentials|/etc/passwd|/etc/shadow|\.bash_history|\.docker/config\.json|\.kube/config|Login Data|keychain", re.I)


def _context_severity(sev, fc, baseline_hit):
    notes = []
    if fc.is_entry or fc.is_hook_target:
        sev = upgrade(sev)
        notes.append("runs at import/install time" if fc.is_entry else "referenced by an install hook")
    if baseline_hit:
        sev = downgrade(sev)
        notes.append("repository already uses this capability (baseline)")
    return sev, notes


class _Aggregating(Detector):
    capability = ""

    def emit(self, ctx, fc, hits, title, base_sev, conf, reason):
        if not hits:
            return []
        hits.sort(key=lambda h: h[0])
        baseline = ctx.baseline.get(self.capability, 0) > 0
        sev, notes = _context_severity(base_sev, fc, baseline)
        evidence = "\n…\n".join(fc.snippet(ln, 1) for ln, _ in hits[:3])
        detail = "; ".join(sorted({d for _, d in hits}))[:300]
        full_reason = f"{reason} ({detail})" + (f". Context: {', '.join(notes)}" if notes else "")
        return [self.finding(title=title, category=self.capability, severity=sev, confidence=conf, reason=full_reason,
                             evidence=evidence, file=fc.path, line=hits[0][0], context={"occurrences": len(hits), "baseline": baseline})]


class DynamicExecDetector(Detector):
    id = "dynamic-exec"
    name = "Dynamic code execution"

    def run(self, ctx):
        out = []
        for fc in ctx.code_files():
            if fc.record.kind == "python":
                out += self._python(ctx, fc)
            elif fc.record.kind == "javascript":
                out += self._js(ctx, fc)
        return out

    def _python(self, ctx, fc):
        facts = PyFacts(fc.text)
        out = []
        for name, node in facts.calls:
            if not fc.in_scope(node.lineno):
                continue
            if name == "getattr" and node.args and getattr(node.args[0], "id", "") in ("__builtins__", "builtins"):
                out.append(self._f(fc, node.lineno, "high", 0.8, "Indirect builtin lookup via getattr(__builtins__, …) hides the called function name"))
                continue
            if name not in PY_EXEC:
                continue
            args = node.args
            nested = facts.nested_call_names(node)
            if name == "__import__" or name == "importlib.import_module":
                if args and not isinstance(args[0], ast.Constant):
                    out.append(self._f(fc, node.lineno, "medium", 0.6, f"{name}() with a computed module name"))
                continue
            if nested & DECODERS:
                out.append(self._f(fc, node.lineno, "critical", 0.92, f"{name}() executes data produced by {', '.join(sorted(nested & DECODERS))}"))
            elif args and isinstance(args[0], ast.Constant):
                out.append(self._f(fc, node.lineno, "low", 0.45, f"{name}() on a literal string"))
            else:
                sev, notes = _context_severity("medium", fc, ctx.baseline.get("exec", 0) > 0)
                out.append(self._f(fc, node.lineno, sev, 0.6, f"{name}() on a computed value" + (f" ({', '.join(notes)})" if notes else "")))
        for node in ast.walk(facts.tree) if facts.ok else []:
            if isinstance(node, ast.Subscript) and getattr(node.value, "id", "") == "__builtins__" and fc.in_scope(node.lineno):
                out.append(self._f(fc, node.lineno, "high", 0.8, "Builtin accessed by subscript on __builtins__ (indirection used to hide exec/eval)"))
        return out

    def _js(self, ctx, fc):
        out = []
        expected_bundle = fc.record.status == "expected"
        for i, line in fc.scoped_lines():
            if not JS_EXEC.search(line):
                continue
            if JS_DECODE.search(line):
                out.append(self._f(fc, i, "critical", 0.9, "Dynamic evaluation of decoded data in the same statement"))
            else:
                sev = "low" if expected_bundle or ctx.baseline.get("exec", 0) else "medium"
                out.append(self._f(fc, i, sev, 0.55, "Dynamic code evaluation (eval/new Function/vm)"))
        return out

    def _f(self, fc, line, sev, conf, reason):
        return self.finding(title="Dynamic code execution", category="exec", severity=sev, confidence=conf, reason=reason,
                            evidence=fc.snippet(line), file=fc.path, line=line)


class ProcessExecDetector(_Aggregating):
    id = "process-exec"
    capability = "process"

    def run(self, ctx):
        out = []
        for fc in ctx.code_files():
            hits, dangerous = [], False
            if fc.record.kind == "python":
                for name, node in PyFacts(fc.text).calls:
                    if name.startswith(PY_PROC) and fc.in_scope(node.lineno):
                        hits.append((node.lineno, name))
            elif fc.record.kind in ("javascript", "shell"):
                for i, line in fc.scoped_lines():
                    if fc.record.kind == "shell" and DANGEROUS_CMD.search(line):
                        hits.append((i, "shell command"))
                    elif JS_PROC.search(line):
                        hits.append((i, "child_process"))
            for ln, _ in hits:
                if DANGEROUS_CMD.search(fc.lines[ln - 1]):
                    dangerous = True
            sev = "high" if dangerous else "medium"
            out += self.emit(ctx, fc, hits, "Spawns operating-system processes", sev, 0.85 if dangerous else 0.6,
                             "Package-introduced code launches external processes" + (" with download/shell primitives" if dangerous else ""))
        return out


class NetworkDetector(_Aggregating):
    id = "network-access"
    capability = "network"

    def run(self, ctx):
        out = []
        for fc in ctx.code_files():
            hits = []
            if fc.record.kind == "python":
                facts = PyFacts(fc.text)
                hits = [(n.lineno, name) for name, n in facts.calls if name.startswith(PY_NET) and fc.in_scope(n.lineno)]
            elif fc.record.kind == "javascript":
                hits = [(i, "network API") for i, line in fc.scoped_lines() if JS_NET.search(line)]
            if hits:
                urls = {u for ln, _ in hits for u in URL_OR_IP.findall(fc.lines[ln - 1])}
                if urls:
                    hits.append((hits[0][0], "hard-coded endpoint " + ", ".join(sorted(urls)[:3])))
            out += self.emit(ctx, fc, hits, "Unexpected network access", "medium", 0.65,
                             "Package-introduced code opens network connections")
        return out


class CredentialAccessDetector(_Aggregating):
    id = "credential-access"
    capability = "credentials"

    def run(self, ctx):
        out = []
        for fc in ctx.code_files():
            hits, bulk = [], False
            for i, line in fc.scoped_lines():
                if ENV_BULK.search(line):
                    hits.append((i, "dumps the entire environment"))
                    bulk = True
                elif SECRET_FILES.search(line):
                    hits.append((i, "reads credential files"))
                    bulk = True
                else:
                    m = ENV_SECRET.search(line)
                    if m:
                        hits.append((i, f"reads secret variable {m.group(1)}"))
            out += self.emit(ctx, fc, hits, "Credential or secret harvesting", "high" if bulk else "medium", 0.75 if bulk else 0.55,
                             "Package-introduced code accesses secrets or credential stores")
        return out
