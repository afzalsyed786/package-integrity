"""Comparison engine: aligns package files to repository files and classifies each one."""
import difflib
import hashlib
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .filetypes import file_kind, read_head, read_text
from .models import FileRecord

SKIP_DIRS = {".git", ".hg", ".svn"}


def walk_files(root: Path | None) -> dict[str, Path]:
    out = {}
    if root is None or not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.is_symlink() or not p.is_file():
                continue
            out[p.relative_to(root).as_posix()] = p
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def best_prefix(pkg_paths, repo_paths, hints) -> str:
    by_name: dict[str, list[str]] = {}
    for r in repo_paths:
        by_name.setdefault(r.rsplit("/", 1)[-1], []).append(r)
    counts = Counter()
    for p in list(pkg_paths)[:3000]:
        for r in by_name.get(p.rsplit("/", 1)[-1], []):
            if r == p:
                counts[""] += 1
            elif r.endswith("/" + p):
                counts[r[: -len(p)]] += 1
    if not counts:
        return ""
    best, n = counts.most_common(1)[0]
    if counts.get("", 0) >= n * 0.8:
        return ""
    return best if best in hints or n >= 2 else ""


def added_lines(old: str, new: str) -> set[int]:
    sm = difflib.SequenceMatcher(None, old.splitlines(), new.splitlines(), autojunk=False)
    added = set()
    for tag, _, _, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            added.update(range(j1 + 1, j2 + 1))
    return added


@dataclass
class ComparisonResult:
    records: list = field(default_factory=list)
    pkg_map: dict = field(default_factory=dict)
    repo_map: dict = field(default_factory=dict)
    mapping: dict = field(default_factory=dict)
    prefix: str = ""
    repo_only: list = field(default_factory=list)


class ComparisonEngine:
    def __init__(self, profile, max_text_bytes: int):
        self.profile = profile
        self.max_text = max_text_bytes

    def _norm(self, rel, text):
        return self.profile.normalize_for_compare(rel, text.replace("\r\n", "\n")).rstrip()

    def compare(self, pkg_root: Path, repo_root: Path | None) -> ComparisonResult:
        pkg_map, repo_map = walk_files(pkg_root), walk_files(repo_root)
        prefix = best_prefix(pkg_map, repo_map, self.profile.source_prefix_hints()) if repo_map else ""
        res = ComparisonResult(pkg_map=pkg_map, repo_map=repo_map, prefix=prefix)
        matched_repo = set()
        for rel, path in sorted(pkg_map.items()):
            kind = file_kind(rel, read_head(path))
            rec = FileRecord(path=rel, status="package_only", kind=kind, size=path.stat().st_size, pkg_sha256=sha256(path))
            rp = prefix + rel if prefix + rel in repo_map else (rel if rel in repo_map else None)
            if rp:
                matched_repo.add(rp)
                res.mapping[rel] = rp
                rec.repo_path = rp
                rec.repo_sha256 = sha256(repo_map[rp])
                if rec.repo_sha256 == rec.pkg_sha256:
                    rec.status = "identical"
                else:
                    a, b = read_text(path, self.max_text), read_text(repo_map[rp], self.max_text)
                    if a is not None and b is not None and self._norm(rel, a) == self._norm(rel, b):
                        rec.status, rec.normalized = "identical", True
                    else:
                        rec.status = "modified"
            res.records.append(rec)
        res.repo_only = sorted(set(repo_map) - matched_repo)
        return res
