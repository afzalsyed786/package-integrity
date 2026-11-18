from dataclasses import dataclass, field
from pathlib import Path

from ..engine.filetypes import CODE_KINDS
from ..engine.models import FileRecord, Finding

DOC_NAMES = ("README", "CHANGELOG", "HISTORY", "LICENSE", "NOTICE", "AUTHORS", "PKG-INFO", "METADATA")


@dataclass
class FileContext:
    record: FileRecord
    abs_path: Path
    text: str | None
    repo_text: str | None = None
    added: set | None = None  # None => every line is new
    is_entry: bool = False
    is_hook_target: bool = False
    _lines: list | None = None

    @property
    def path(self) -> str:
        return self.record.path

    @property
    def lines(self) -> list[str]:
        if self._lines is None:
            self._lines = (self.text or "").splitlines()
        return self._lines

    def in_scope(self, lineno: int | None) -> bool:
        return self.added is None or (lineno is not None and lineno in self.added)

    def scoped_lines(self):
        for i, line in enumerate(self.lines, 1):
            if self.in_scope(i):
                yield i, line

    @property
    def is_code(self) -> bool:
        return self.record.kind in CODE_KINDS and self.text is not None

    @property
    def is_doc(self) -> bool:
        return self.record.path.split("/")[-1].upper().startswith(DOC_NAMES) or self.record.kind in ("doc", "metadata")

    def snippet(self, lineno: int | None, radius: int = 2, max_len: int = 900) -> str:
        if not lineno or not self.lines:
            return ""
        lo, hi = max(1, lineno - radius), min(len(self.lines), lineno + radius)
        out = []
        for i in range(lo, hi + 1):
            mark = ">" if i == lineno else " "
            line = self.lines[i - 1]
            out.append(f"{mark}{i:5d} | {line[:240]}{'…' if len(line) > 240 else ''}")
        text = "\n".join(out)
        return text[:max_len]


@dataclass
class AnalysisContext:
    release: object
    source: object
    profile: object
    files: list
    records: list
    pkg_root: Path
    repo_root: Path | None
    pkg_map: dict
    repo_map: dict
    archive_report: object
    hooks: list = field(default_factory=list)
    repo_hooks: list = field(default_factory=list)
    manifest: dict | None = None
    baseline: dict = field(default_factory=dict)
    sourcemaps: dict = field(default_factory=dict)
    artifact: dict = field(default_factory=dict)
    max_text: int = 2 * 1024 * 1024

    def file(self, rel: str) -> FileContext | None:
        return next((f for f in self.files if f.path == rel), None)

    def code_files(self):
        return [f for f in self.files if f.is_code]


class Detector:
    id = "base"
    name = "Base detector"
    description = ""

    def run(self, ctx: AnalysisContext) -> list[Finding]:
        raise NotImplementedError

    def finding(self, **kw) -> Finding:
        kw.setdefault("rule_id", self.id)
        return Finding(**kw)
