"""Optional AI explanation. The model only explains; it never decides the verdict."""
from datetime import datetime, timezone

import requests

from .redaction import redact

PROVIDERS = {
    "groq": {"url": "https://api.groq.com/openai/v1/chat/completions", "default_model": "llama-3.3-70b-versatile"},
    "openrouter": {"url": "https://openrouter.ai/api/v1/chat/completions", "default_model": "meta-llama/llama-3.3-70b-instruct"},
}
DISCLAIMER = ("AI-generated explanation of deterministic findings. It does not influence the verdict, "
              "which is computed solely by PIA's rule and scoring engine.")
SYSTEM_PROMPT = (
    "You are a software supply-chain security analyst. You receive findings produced by a deterministic "
    "package-integrity scanner, each with a minimal redacted evidence snippet. Explain in plain language what each "
    "finding means, how an attacker could abuse it, and what a reviewer should check next. Do NOT issue or change a "
    "verdict and do not invent facts beyond the evidence. Use concise markdown with sections: Summary, Findings, "
    "Recommended next steps."
)


class ExplanationService:
    def __init__(self, settings):
        self.s = settings

    def _provider(self):
        name = self.s.ai_provider if self.s.ai_provider in PROVIDERS else "groq"
        key = self.s.groq_api_key if name == "groq" else self.s.openrouter_api_key
        return name, PROVIDERS[name], key, self.s.ai_model or PROVIDERS[name]["default_model"]

    def status(self) -> dict:
        name, _, key, model = self._provider()
        return {"provider": name, "model": model, "configured": bool(key), "providers": list(PROVIDERS)}

    def build_payload(self, analysis: dict, max_findings: int = 6) -> dict:
        ranked = [f for f in analysis.get("findings", []) if f["severity"] in ("medium", "high", "critical")]
        items = [{
            "rule": f["rule_id"], "severity": f["severity"], "file": f.get("file"), "line": f.get("line"),
            "reason": redact(f["reason"], 300), "snippet": redact(f.get("evidence", ""), 600),
        } for f in ranked[:max_findings]]
        return {
            "package": f"{analysis['ecosystem']}:{analysis['package']}@{analysis['version']}",
            "deterministic_verdict": analysis["verdict"], "risk_score": analysis["risk_score"],
            "findings": items,
        }

    def explain(self, analysis: dict) -> dict:
        name, prov, key, model = self._provider()
        payload = self.build_payload(analysis)
        base = {"provider": name, "model": model, "payload": payload, "disclaimer": DISCLAIMER,
                "created_at": datetime.now(timezone.utc).isoformat()}
        if not key:
            return {**base, "status": "disabled", "text": f"AI explanations are disabled. Set {name.upper()}_API_KEY to enable."}
        if not payload["findings"]:
            return {**base, "status": "ok", "text": "No medium or higher findings to explain."}
        body = {"model": model, "temperature": 0.2, "max_tokens": 900, "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _format(payload)}]}
        try:
            r = requests.post(prov["url"], json=body, timeout=self.s.ai_timeout,
                              headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            return {**base, "status": "ok", "text": text}
        except (requests.RequestException, KeyError, ValueError) as e:
            return {**base, "status": "error", "text": f"AI provider request failed: {str(e)[:200]}"}


def _format(payload: dict) -> str:
    lines = [f"Package: {payload['package']}", f"Deterministic verdict (final, do not change): {payload['deterministic_verdict']}", ""]
    for i, f in enumerate(payload["findings"], 1):
        lines += [f"{i}. [{f['severity']}] {f['rule']} in {f['file']}:{f['line']}", f"   Reason: {f['reason']}", f"   Snippet:\n{f['snippet']}", ""]
    return "\n".join(lines)
