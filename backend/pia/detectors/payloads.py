"""Encoded payloads, high-entropy strings and obfuscation. Context-aware: data URIs, maps, lock files and
build outputs with verified source maps are not treated like hand-written code."""
import base64
import binascii
import re
import zlib

from ..services.redaction import shannon_entropy
from .base import Detector

B64 = re.compile(r"(?<![A-Za-z0-9+/=_-])([A-Za-z0-9+/]{60,}={0,2}|[A-Za-z0-9_-]{80,}={0,2})(?![A-Za-z0-9+/=_-])")
HEX = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{120,})(?![0-9a-fA-F])")
STRING_LIT = re.compile(r"(['\"])((?:(?!\1).){50,})\1")
CODE_TOKENS = re.compile(r"\b(import|exec|eval|subprocess|socket|urlopen|require\(|child_process|/bin/sh|powershell|os\.system|process\.env|fetch\(|http[s]?://)")
SKIP_EXT = (".map", ".lock", ".svg", ".min.css", "package-lock.json", "yarn.lock", "RECORD", "SOURCES.txt")
HASH_LENGTHS = {32, 40, 56, 64, 96, 128}


def _decode_b64(s: str) -> bytes | None:
    try:
        pad = s + "=" * (-len(s) % 4)
        return base64.b64decode(pad, altchars=b"-_" if ("-" in s or "_" in s) else None, validate=False)
    except (binascii.Error, ValueError):
        return None


def _inflate(data: bytes) -> bytes | None:
    for wbits in (15, 31, -15):
        try:
            d = zlib.decompressobj(wbits)
            out = d.decompress(data, 65536)
            if out:
                return out
        except zlib.error:
            continue
    return None


def _printable(data: bytes) -> float:
    if not data:
        return 0.0
    return sum(32 <= b < 127 or b in (9, 10, 13) for b in data) / len(data)


def _scannable(fc) -> bool:
    return fc.is_code and not fc.path.endswith(SKIP_EXT)


class EncodedPayloadDetector(Detector):
    id = "encoded-payload"

    def run(self, ctx):
        out = []
        for fc in ctx.files:
            if not _scannable(fc):
                continue
            for i, line in fc.scoped_lines():
                for m in B64.finditer(line):
                    blob = m.group(1)
                    if "base64," in line[max(0, m.start() - 40):m.start()] or shannon_entropy(blob) < 4.0:
                        continue
                    f = self._assess(fc, i, blob, "Base64")
                    if f:
                        out.append(f)
                for m in HEX.finditer(line):
                    f = self._assess(fc, i, m.group(1), "hex", binascii.unhexlify(m.group(1)[: len(m.group(1)) // 2 * 2]))
                    if f:
                        out.append(f)
        return out

    def _assess(self, fc, line, blob, enc, raw=None):
        raw = raw if raw is not None else _decode_b64(blob)
        if not raw:
            return None
        layer = ""
        inflated = _inflate(raw) if raw[:1] in (b"\x78", b"\x1f") or _printable(raw) < 0.6 else None
        if inflated:
            raw, layer = inflated, " + zlib/gzip"
        preview = raw[:400].decode("utf-8", "replace")
        tokens = sorted(set(CODE_TOKENS.findall(preview))) if _printable(raw) > 0.85 else []
        evidence = fc.snippet(line, 0) + f"\n\n[decoded {enc}{layer}, {len(raw)} bytes]\n{preview}"
        if tokens:
            return self.finding(title=f"Encoded executable payload ({enc}{layer})", category="encoded", severity="high", confidence=0.85,
                                reason=f"A {len(blob)}-char {enc} literal decodes to code-like content ({', '.join(tokens[:6])})",
                                evidence=evidence, file=fc.path, line=line)
        if layer:
            return self.finding(title="Compressed encoded blob", category="encoded", severity="medium", confidence=0.6,
                                reason=f"{enc} literal decodes to compressed binary data", evidence=evidence, file=fc.path, line=line)
        return None


class HighEntropyDetector(Detector):
    id = "high-entropy"

    def run(self, ctx):
        out = []
        for fc in ctx.files:
            if not _scannable(fc) or fc.record.status == "expected":
                continue
            hits = []
            for i, line in fc.scoped_lines():
                for m in STRING_LIT.finditer(line):
                    s = m.group(2)
                    if " " in s or (len(s) in HASH_LENGTHS and re.fullmatch(r"[0-9a-fA-F]+", s)):
                        continue
                    e = shannon_entropy(s)
                    if e >= 4.6:
                        hits.append((i, len(s), e))
            if hits:
                ln, size, e = max(hits, key=lambda h: h[2])
                out.append(self.finding(title="High-entropy string literals", category="entropy", severity="medium" if len(hits) > 1 or size > 200 else "low",
                                        confidence=0.5, reason=f"{len(hits)} string literal(s) with entropy up to {e:.2f} bits/char (max {size} chars) in package-introduced code",
                                        evidence=fc.snippet(ln, 0), file=fc.path, line=ln, context={"count": len(hits)}))
        return out


OBF_PATTERNS = [
    (re.compile(r"\b_0x[0-9a-f]{4,6}\b"), "javascript-obfuscator style _0x identifiers", 5, 3),
    (re.compile(r"chr\(\s*\d+\s*\)"), "chr() character assembly", 6, 2),
    (re.compile(r"''\.join\(\s*chr\(|\"\"\.join\(\s*chr\(|\.join\(\s*map\(\s*chr"), "string built from character codes", 1, 3),
    (re.compile(r"String\.fromCharCode\((?:\s*\d+\s*,){6,}"), "String.fromCharCode with numeric arrays", 1, 3),
    (re.compile(r"(?:\\x[0-9a-fA-F]{2}){12,}"), "long hex-escape sequences", 1, 2),
    (re.compile(r"\[::-1\]"), "string reversal", 1, 1),
    (re.compile(r"getattr\(\s*__builtins__|__builtins__\s*\["), "builtin indirection", 1, 3),
    (re.compile(r"lambda\s+\w*\s*:\s*__import__"), "lambda-wrapped __import__", 1, 2),
]


class ObfuscationDetector(Detector):
    id = "obfuscation"

    def run(self, ctx):
        out = []
        for fc in ctx.files:
            if not _scannable(fc):
                continue
            score, reasons, first = 0, [], None
            scoped = list(fc.scoped_lines())
            body = "\n".join(line for _, line in scoped)
            for pat, label, threshold, weight in OBF_PATTERNS:
                n = len(pat.findall(body))
                if n >= threshold:
                    score += weight
                    reasons.append(f"{label} ×{n}")
                    if first is None:
                        first = next((i for i, line in scoped if pat.search(line)), None)
            long_lines = [i for i, line in scoped if len(line) > 800]
            if long_lines and fc.record.status != "expected" and not fc.path.endswith(".min.js"):
                score += 2
                reasons.append(f"{len(long_lines)} very long line(s) in non-build file")
                first = first or long_lines[0]
            if score >= 3:
                sev = "high" if score >= 5 else "medium"
                out.append(self.finding(title="Obfuscated code", category="obfuscation", severity=sev, confidence=0.75 if sev == "high" else 0.6,
                                        reason="Obfuscation indicators: " + "; ".join(reasons), evidence=fc.snippet(first),
                                        file=fc.path, line=first, context={"obfuscation_score": score}))
        return out
