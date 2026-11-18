"""Safe archive inspector: extracts untrusted archives without ever trusting member metadata."""
import os
import stat
import tarfile
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


class ArchiveError(Exception):
    pass


class _TooBig(Exception):
    pass


@dataclass
class RejectedEntry:
    name: str
    kind: str
    reason: str
    target: str | None = None


@dataclass
class ExtractionReport:
    root: Path
    archive_type: str
    files: list = field(default_factory=list)
    rejected: list = field(default_factory=list)
    total_bytes: int = 0

    def to_dict(self) -> dict:
        return {
            "archive_type": self.archive_type,
            "file_count": len(self.files),
            "total_bytes": self.total_bytes,
            "rejected": [asdict(r) for r in self.rejected],
        }


EXPECTED_BY_SUFFIX = {
    ".whl": "zip", ".zip": "zip", ".egg": "zip", ".tgz": "tar.gz", ".gz": "tar.gz",
    ".bz2": "tar.bz2", ".xz": "tar.xz", ".tar": "tar",
}
TAR_MODES = {"tar.gz": "r:gz", "tar.bz2": "r:bz2", "tar.xz": "r:xz", "tar": "r:"}


def sniff_archive_type(path: Path) -> str:
    with open(path, "rb") as fh:
        head = fh.read(262)
    if head.startswith(b"\x1f\x8b"):
        return "tar.gz"
    if head.startswith((b"PK\x03\x04", b"PK\x05\x06")):
        return "zip"
    if head.startswith(b"BZh"):
        return "tar.bz2"
    if head.startswith(b"\xfd7zXZ\x00"):
        return "tar.xz"
    if len(head) >= 262 and head[257:262] == b"ustar":
        return "tar"
    raise ArchiveError("unrecognised or unsupported archive format (file-type validation failed)")


def validate_type(path: Path, filename: str) -> str:
    actual = sniff_archive_type(path)
    expected = EXPECTED_BY_SUFFIX.get(Path(filename).suffix.lower())
    if expected and expected != actual:
        raise ArchiveError(f"file type mismatch: name suggests {expected} but content is {actual}")
    return actual


def safe_member_path(name: str) -> str | None:
    if not name or "\x00" in name:
        return None
    n = name.replace("\\", "/")
    if n.startswith("/") or (len(n) > 1 and n[1] == ":"):
        return None
    parts = [p for p in n.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    return "/".join(parts)


def _link_escapes(member_rel: str, target: str) -> bool:
    if target.startswith("/") or (len(target) > 1 and target[1] == ":"):
        return True
    depth = len(member_rel.split("/")) - 1
    for part in target.replace("\\", "/").split("/"):
        if part == "..":
            depth -= 1
            if depth < 0:
                return True
        elif part not in ("", "."):
            depth += 1
    return False


class SafeArchiveInspector:
    def __init__(self, limits):
        self.l = limits

    def extract(self, archive: Path, dest: Path, filename: str | None = None) -> ExtractionReport:
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        atype = validate_type(Path(archive), filename or Path(archive).name)
        rep = ExtractionReport(root=dest, archive_type=atype)
        if atype == "zip":
            self._zip(Path(archive), dest, rep)
        else:
            self._tar(Path(archive), dest, rep, TAR_MODES[atype])
        return rep

    def _reject(self, rep, name, kind, reason, target=None):
        rep.rejected.append(RejectedEntry(name=name, kind=kind, reason=reason, target=target))

    def _target(self, dest: Path, rel: str) -> Path | None:
        target = (dest / rel).resolve()
        return target if target.is_relative_to(dest.resolve()) else None

    def _account(self, rep, size):
        if len(rep.files) >= self.l.max_files:
            raise ArchiveError(f"archive contains more than {self.l.max_files} files")
        if rep.total_bytes + size > self.l.max_extract_bytes:
            raise ArchiveError("total extracted size exceeds limit")

    def _write(self, src, target: Path) -> int:
        target.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(target, flags, 0o644)
        written = 0
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = src.read(65536)
                if not chunk:
                    break
                written += len(chunk)
                if written > self.l.max_file_bytes:
                    raise _TooBig()
                out.write(chunk)
        return written

    def _store(self, rep, dest, rel, name, size, opener):
        if size > self.l.max_file_bytes:
            return self._reject(rep, name, "oversize", f"member size {size} exceeds per-file limit")
        self._account(rep, size)
        target = self._target(dest, rel)
        if target is None:
            return self._reject(rep, name, "path_traversal", "resolved path escapes extraction directory")
        if target.exists():
            return self._reject(rep, name, "duplicate", "duplicate archive member (possible shadowing)")
        try:
            with opener() as src:
                n = self._write(src, target)
        except _TooBig:
            target.unlink(missing_ok=True)
            return self._reject(rep, name, "oversize", "decompressed data exceeds per-file limit")
        except OSError as e:
            return self._reject(rep, name, "conflict", f"could not materialise member safely: {e.strerror}")
        rep.total_bytes += n
        rep.files.append(rel)

    def _tar(self, archive, dest, rep, mode):
        try:
            tf = tarfile.open(archive, mode)
        except (tarfile.TarError, OSError, EOFError) as e:
            raise ArchiveError(f"corrupt archive: {e}") from e
        with tf:
            seen = 0
            try:
                for m in tf:
                    seen += 1
                    if seen > self.l.max_files * 2:
                        raise ArchiveError("too many archive entries")
                    rel = safe_member_path(m.name)
                    if rel is None:
                        self._reject(rep, m.name, "path_traversal", "absolute path or '..' component would escape extraction directory")
                    elif m.issym():
                        kind = "symlink_escape" if _link_escapes(rel, m.linkname) else "symlink"
                        self._reject(rep, m.name, kind, "symbolic links are never materialised", m.linkname)
                    elif m.islnk():
                        self._reject(rep, m.name, "hardlink", "hard links are never materialised", m.linkname)
                    elif m.isdir():
                        continue
                    elif not m.isfile():
                        self._reject(rep, m.name, "special_file", "device, FIFO or other special file rejected")
                    else:
                        member = m
                        self._store(rep, dest, rel, m.name, m.size, lambda: tf.extractfile(member))
            except (tarfile.TarError, EOFError, OSError) as e:
                raise ArchiveError(f"corrupt archive: {e}") from e

    def _zip(self, archive, dest, rep):
        try:
            zf = zipfile.ZipFile(archive)
        except (zipfile.BadZipFile, OSError) as e:
            raise ArchiveError(f"corrupt zip archive: {e}") from e
        with zf:
            infos = zf.infolist()
            if len(infos) > self.l.max_files * 2:
                raise ArchiveError("too many archive entries")
            for info in infos:
                rel = safe_member_path(info.filename)
                ftype = (info.external_attr >> 16) & 0o170000
                if rel is None:
                    self._reject(rep, info.filename, "path_traversal", "absolute path or '..' component would escape extraction directory")
                elif ftype == stat.S_IFLNK:
                    target = zf.read(info)[:1024].decode("utf-8", "replace")
                    kind = "symlink_escape" if _link_escapes(rel, target) else "symlink"
                    self._reject(rep, info.filename, kind, "symbolic links are never materialised", target)
                elif info.is_dir():
                    continue
                elif ftype and ftype != stat.S_IFREG:
                    self._reject(rep, info.filename, "special_file", "special file type rejected")
                elif info.flag_bits & 0x1:
                    self._reject(rep, info.filename, "encrypted", "encrypted members cannot be inspected")
                elif info.compress_size and info.file_size > 1_000_000 and info.file_size / info.compress_size > self.l.max_compression_ratio:
                    self._reject(rep, info.filename, "zip_bomb", f"compression ratio {info.file_size // info.compress_size}:1 exceeds limit")
                else:
                    member = info
                    self._store(rep, dest, rel, info.filename, info.file_size, lambda: zf.open(member))


def single_top_dir(root: Path, files: list[str]) -> Path:
    tops = {f.split("/", 1)[0] for f in files}
    if len(tops) == 1 and all("/" in f for f in files):
        return root / tops.pop()
    return root
