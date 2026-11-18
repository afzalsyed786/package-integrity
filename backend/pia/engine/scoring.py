"""Explainable scoring: per-finding scores, correlation, noisy-OR aggregation and verdict rules."""
from collections import defaultdict

from .filetypes import CODE_KINDS
from .models import SEVERITY_BASE, Finding

COMBOS = [
    ({"network", "credentials"}, "Credential exfiltration pattern"),
    ({"encoded", "exec"}, "Encoded payload is executed"),
    ({"network", "exec"}, "Staged remote payload pattern"),
    ({"network", "process"}, "Network-connected process execution"),
    ({"obfuscation", "exec"}, "Obfuscated dynamic execution"),
    ({"install", "exec"}, "Install hook executes dynamic code"),
]
SUSPICIOUS_THRESHOLD = 60
REVIEW_THRESHOLD = 30


def combine(scores) -> int:
    remaining = 1.0
    for s in scores:
        remaining *= 1 - min(s, 99) / 100
    return round(100 * (1 - remaining))


def correlate(findings: list[Finding]) -> list[Finding]:
    by_file = defaultdict(list)
    for f in findings:
        if f.file and f.severity in ("medium", "high", "critical"):
            by_file[f.file].append(f)
    out = []
    for file, fs in by_file.items():
        cats = {f.category for f in fs}
        for need, title in COMBOS:
            if need <= cats:
                parts = [f for f in fs if f.category in need]
                out.append(Finding(rule_id="correlation", title=title, category="correlation", severity="critical", confidence=0.85,
                                   reason=f"{' + '.join(sorted(need))} behaviours co-occur in the same file — a classic multi-stage malware structure",
                                   evidence="\n".join(f"- {p.title} (line {p.line}): {p.reason[:140]}" for p in parts), file=file,
                                   line=parts[0].line, context={"components": [p.id for p in parts]}))
                break
    return out


def coverage(records) -> float:
    code = [r for r in records if r.kind in CODE_KINDS | {"bytecode", "native"}]
    if not code:
        return 1.0
    return round(sum(r.status in ("identical", "expected") for r in code) / len(code), 3)


def score(findings: list[Finding], records, source, errors: list[str]) -> dict:
    findings = findings + correlate(findings)
    for f in findings:
        f.score = round(SEVERITY_BASE[f.severity] * f.confidence)
    findings.sort(key=lambda f: (-f.score, f.file or ""))
    risk = combine(f.score for f in findings)
    for rec in records:
        mine = [f.score for f in findings if f.file == rec.path]
        rec.risk_score, rec.finding_count = combine(mine), len(mine)
    cov = coverage(records) if source.comparable else 0.0
    strong = [f for f in findings if (f.severity == "critical" and f.confidence >= 0.6) or (f.severity == "high" and f.confidence >= 0.7)]
    reasons = []
    if strong or risk >= SUSPICIOUS_THRESHOLD:
        verdict = "Suspicious"
        reasons += list(dict.fromkeys(f"{f.severity.upper()}: {f.title}" + (f" in {f.file}" if f.file else "") + (f":{f.line}" if f.line else "") for f in strong))[:6]
        if risk >= SUSPICIOUS_THRESHOLD:
            reasons.append(f"Aggregate risk {risk} ≥ {SUSPICIOUS_THRESHOLD}")
    else:
        if not source.comparable:
            reasons.append(f"Source comparison unavailable ({source.status})")
        elif source.is_fallback:
            reasons.append("No release tag: compared against default-branch snapshot only")
        if source.comparable and cov < 0.5:
            reasons.append(f"Only {cov:.0%} of package code could be matched or explained (unsupported build style?)")
        if errors:
            reasons.append(f"{len(errors)} analysis step(s) failed")
        if risk >= REVIEW_THRESHOLD:
            reasons.append(f"Moderate aggregate risk {risk} requires manual review")
        verdict = "Inconclusive" if reasons else "Clean"
        if verdict == "Clean":
            reasons.append(f"{cov:.0%} of code files identical to or explained by source; no high-severity findings; risk {risk}")
    counts = defaultdict(int)
    cats = defaultdict(int)
    for f in findings:
        counts[f.severity] += 1
        cats[f.category] += 1
    return {"verdict": verdict, "risk_score": risk, "verdict_reasons": reasons, "coverage": cov, "findings": findings,
            "severity_counts": dict(counts), "category_counts": dict(cats)}
