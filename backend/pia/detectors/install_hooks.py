import re

from .base import Detector


class InstallHookDetector(Detector):
    id = "install-hook"

    def run(self, ctx):
        out = []
        repo_keys = {(h["kind"], h.get("detail")) for h in ctx.repo_hooks}
        repo_kinds = {h["kind"] for h in ctx.repo_hooks}
        package_only = {f.path for f in ctx.files if f.record.status == "package_only"}
        for h in ctx.hooks:
            fc = ctx.file(h["file"])
            evidence = fc.snippet(h["line"], 3) if fc and h.get("line") else h["detail"]
            targets = [t.lstrip("./") for t in re.findall(r"[\w./-]+\.(?:c|m)?js|[\w./-]+\.py|[\w./-]+\.sh", h.get("command", ""))]
            hits_new_file = [t for t in targets if t in package_only]
            if (h["kind"], h.get("detail")) in repo_keys:
                out.append(self.finding(title="Install hook present in source", category="install", severity="info", confidence=0.4,
                                        reason=f"{h['detail']} — also declared in the repository (baseline behaviour)", evidence=evidence, file=h["file"], line=h.get("line")))
            elif h["kind"] in repo_kinds:
                out.append(self.finding(title="Install hook changed versus source", category="install", severity="high", confidence=0.75,
                                        reason=f"{h['detail']} — the repository declares a different hook of this type", evidence=evidence, file=h["file"], line=h.get("line")))
            else:
                sev = "critical" if hits_new_file else "high"
                out.append(self.finding(title="Unexpected install-time hook", category="install", severity=sev, confidence=0.85,
                                        reason=f"{h['detail']} — not present in the source repository" +
                                        (f"; runs package-only file(s) {', '.join(hits_new_file)}" if hits_new_file else ""),
                                        evidence=evidence, file=h["file"], line=h.get("line"), context={"hook": h}))
        return out
