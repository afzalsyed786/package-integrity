"""Artifact detectors: untracked files, native binaries, build-manifest integrity and Python bytecode."""
import importlib.util
import marshal
import re
import types
from pathlib import PurePosixPath

from ..adapters.pypi import record_hash_matches
from ..engine.filetypes import CODE_KINDS
from .base import Detector

SUSPICIOUS_NAMES = {"exec", "eval", "compile", "system", "popen", "Popen", "urlopen", "b64decode", "decompress", "socket",
                    "create_connection", "connect", "getattr", "__import__", "loads", "environ", "check_output", "spawn"}
PRINTABLE_STR = re.compile(rb"[\x20-\x7e]{5,}")


class UntrackedFileDetector(Detector):
    id = "untracked-file"

    def run(self, ctx):
        out, benign = [], []
        for fc in ctx.files:
            rec = fc.record
            if rec.status != "package_only" or rec.kind == "bytecode":
                continue
            if rec.kind == "native":
                out.append(self.finding(title="Native executable without source", category="untracked", severity="high", confidence=0.75,
                                        reason=f"Compiled binary ({rec.size} bytes) present in the package but absent from the repository",
                                        evidence=f"{rec.path}  sha256={rec.pkg_sha256}", file=rec.path))
            elif rec.kind in CODE_KINDS:
                sev = "high" if (fc.is_entry or fc.is_hook_target or rec.kind == "pth") else "medium"
                out.append(self.finding(title="Code file not present in source repository", category="untracked", severity=sev,
                                        confidence=0.7, reason="Executable code shipped in the package has no counterpart at the resolved source revision"
                                        + (" and is reachable at install/import time" if sev == "high" else ""),
                                        evidence=fc.snippet(1, 4) if fc.text else rec.path, file=rec.path, line=1))
            else:
                benign.append(rec.path)
        if benign:
            out.append(self.finding(title="Untracked non-code files", category="untracked", severity="info", confidence=0.3,
                                    reason=f"{len(benign)} data/document file(s) exist only in the package", evidence="\n".join(benign[:15])))
        return out


class ManifestIntegrityDetector(Detector):
    id = "manifest-integrity"

    def run(self, ctx):
        m = ctx.manifest
        if not m:
            return []
        out = []
        entries = m["entries"]
        meta_dir = m["file"].rsplit("/", 1)[0]
        if m["type"] == "RECORD":
            for fc in ctx.files:
                if fc.path == m["file"]:
                    continue
                if fc.path not in entries:
                    out.append(self._f("File missing from wheel RECORD", "high", 0.8, fc.path,
                                       "File is not listed in the wheel's RECORD manifest — added after the wheel was built"))
                elif not record_hash_matches(entries[fc.path], fc.abs_path.read_bytes()):
                    out.append(self._f("RECORD hash mismatch", "critical", 0.9, fc.path,
                                       f"Content hash differs from RECORD entry {entries[fc.path]} — file modified after build"))
        else:
            listed = {e.lstrip("./") for e in entries}
            for fc in ctx.files:
                p = fc.path
                if p in listed or p.startswith(meta_dir + "/") or p in ("PKG-INFO", "setup.cfg") or fc.record.kind not in CODE_KINDS | {"bytecode", "native"}:
                    continue
                out.append(self._f("Code file missing from build manifest", "medium", 0.65, p,
                                   f"Not listed in {m['file']}; files injected after `sdist` was generated are typically absent"))
        return out

    def _f(self, title, sev, conf, path, reason):
        return self.finding(title=title, category="manifest", severity=sev, confidence=conf, reason=reason, evidence=path, file=path)


def _code_names(code, depth=0) -> tuple[set, list]:
    names, strings = set(code.co_names) | set(code.co_varnames), []
    for c in code.co_consts:
        if isinstance(c, str):
            strings.append(c)
        elif isinstance(c, types.CodeType) and depth < 20:
            n, s = _code_names(c, depth + 1)
            names |= n
            strings += s
    return names, strings


def inspect_pyc(data: bytes) -> dict:
    """Parse a .pyc header and code object without executing it."""
    info = {"magic_match": data[:4] == importlib.util.MAGIC_NUMBER, "names": set(), "strings": [], "parsed": False}
    if info["magic_match"] and len(data) <= 5 * 1024 * 1024:
        try:
            code = marshal.loads(data[16:])
            if isinstance(code, types.CodeType):
                info["names"], info["strings"] = _code_names(code)
                info["parsed"] = True
        except (ValueError, EOFError, TypeError):
            pass
    if not info["parsed"]:
        info["strings"] = [s.decode() for s in PRINTABLE_STR.findall(data)][:300]
        info["names"] = {s for s in info["strings"] if s.isidentifier()}
    return info


class BytecodeDetector(Detector):
    id = "bytecode"

    def run(self, ctx):
        out = []
        for fc in ctx.files:
            if fc.record.kind != "bytecode" or fc.record.status == "identical":
                continue
            info = inspect_pyc(fc.abs_path.read_bytes())
            sus = sorted(info["names"] & SUSPICIOUS_NAMES)
            urls = [s for s in info["strings"] if "://" in s or re.search(r"\d+\.\d+\.\d+\.\d+", s)][:5]
            p = PurePosixPath(fc.path)
            parent = p.parent.parent if p.parent.name == "__pycache__" else p.parent
            src_rel = (parent / (p.name.split(".")[0] + ".py")).as_posix()
            source = ctx.pkg_map.get(src_rel) or ctx.repo_map.get(src_rel)
            evidence = (f"magic matches running interpreter: {info['magic_match']}; parsed code object: {info['parsed']}\n"
                        f"suspicious names: {', '.join(sus) or 'none'}\nembedded endpoints: {', '.join(urls) or 'none'}")
            if source is None:
                sev = "critical" if sus and urls else "high"
                out.append(self.finding(title="Compiled bytecode with no corresponding source", category="bytecode", severity=sev, confidence=0.85,
                                        reason="Python bytecode ships without any matching .py source in the package or repository; it cannot be reviewed",
                                        evidence=evidence, file=fc.path, context={"names": sus, "endpoints": urls}))
                continue
            if info["parsed"]:
                try:
                    src_code = compile(source.read_text("utf-8", "replace"), src_rel, "exec")  # compile only
                    extra = sorted((info["names"] - _code_names(src_code)[0]) & SUSPICIOUS_NAMES)
                except (SyntaxError, ValueError):
                    extra = []
                if extra:
                    out.append(self.finding(title="Bytecode does not match its source", category="bytecode", severity="critical", confidence=0.85,
                                            reason=f"Bytecode references names absent from {src_rel}: {', '.join(extra)}",
                                            evidence=evidence, file=fc.path))
        return out
