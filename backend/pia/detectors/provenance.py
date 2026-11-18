from .base import Detector

REJECTION_SEVERITY = {
    "path_traversal": ("critical", 0.95, "Archive member attempts to escape the extraction directory (path traversal)"),
    "symlink_escape": ("high", 0.85, "Symbolic link points outside the package (possible file overwrite or exfiltration)"),
    "symlink": ("low", 0.5, "Symbolic link inside the package (not materialised)"),
    "hardlink": ("medium", 0.6, "Hard link entry (not materialised)"),
    "special_file": ("high", 0.75, "Device/FIFO special file inside a package archive"),
    "duplicate": ("high", 0.7, "Duplicate archive member names can hide content from reviewers"),
    "zip_bomb": ("high", 0.8, "Compression ratio indicates a decompression bomb"),
    "oversize": ("medium", 0.5, "Member exceeds the per-file inspection limit and was skipped"),
    "encrypted": ("medium", 0.6, "Encrypted member cannot be inspected"),
    "conflict": ("medium", 0.5, "Member path conflicts with another entry"),
}


class ProvenanceDetector(Detector):
    id = "provenance"

    def run(self, ctx):
        out = []
        src = ctx.source
        if src.status == "no_repo":
            out.append(self._f("No source repository declared", "medium", 0.6, "Registry metadata does not link a recognised source repository; provenance cannot be verified",
                               "repository URLs: " + (", ".join(ctx.release.repo_urls) or "none")))
        elif src.status == "unreachable":
            out.append(self._f("Source repository unreachable", "low", 0.5, "; ".join(src.notes), src.repo or ""))
        elif src.status == "missing":
            out.append(self._f("Missing release tag", "medium", 0.55,
                               f"No tag in {src.repo} matches version {ctx.release.version}. " + " ".join(src.notes),
                               f"candidates tried: {', '.join(src.candidates)}\nclosest tags: {', '.join(src.nearby_tags) or 'none'}"))
        elif src.status == "mismatched":
            out.append(self._f("Release tag does not match published commit", "high", 0.75, " ".join(src.notes),
                               f"tag {src.tag} -> {src.commit}\nregistry gitHead -> {src.expected_commit}"))
        art = ctx.artifact
        if art.get("hash_verified") is False:
            out.append(self._f("Artifact hash mismatch", "critical", 0.95, "Downloaded artifact does not match the registry-published digest",
                               f"expected {art.get('expected_hashes')}\nactual sha256 {art.get('sha256')}"))
        for r in ctx.archive_report.rejected:
            sev, conf, reason = REJECTION_SEVERITY.get(r.kind, ("medium", 0.5, "Rejected archive member"))
            out.append(self.finding(title=f"Unsafe archive entry: {r.kind.replace('_', ' ')}", category="archive", severity=sev, confidence=conf,
                                    reason=f"{reason}. {r.reason}.", evidence=f"member: {r.name}" + (f"\nlink target: {r.target}" if r.target else ""),
                                    file=r.name))
        return out

    def _f(self, title, sev, conf, reason, evidence):
        return self.finding(title=title, category="provenance", severity=sev, confidence=conf, reason=reason, evidence=evidence)
