import math
import re
from collections import Counter

SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "<REDACTED_PRIVATE_KEY>"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "<REDACTED_AWS_KEY>"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "<REDACTED_GITHUB_TOKEN>"),
    (re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b"), "<REDACTED_NPM_TOKEN>"),
    (re.compile(r"\bpypi-[A-Za-z0-9_-]{20,}\b"), "<REDACTED_PYPI_TOKEN>"),
    (re.compile(r"\b(?:sk|gsk|xox[abp])[-_][A-Za-z0-9_-]{16,}\b"), "<REDACTED_API_KEY>"),
    (re.compile(r"(?i)((?:api[_-]?key|token|secret|passw(?:or)?d|authorization)\s*[:=]\s*['\"])[^'\"]{6,}(['\"])"), r"\1<REDACTED>\2"),
]
BLOB = re.compile(r"[A-Za-z0-9+/=_-]{48,}")


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def redact(text: str, max_len: int = 700) -> str:
    out = text or ""
    for pat, repl in SECRET_PATTERNS:
        out = pat.sub(repl, out)
    out = BLOB.sub(lambda m: f"<BLOB len={len(m.group())} entropy={shannon_entropy(m.group()):.1f}>", out)
    return out if len(out) <= max_len else out[:max_len] + " …[truncated]"
