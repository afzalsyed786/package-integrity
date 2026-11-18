from pathlib import Path

EXT_KIND = {
    ".py": "python", ".pyw": "python", ".pyi": "python", ".pth": "pth", ".pyc": "bytecode", ".pyo": "bytecode",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript", ".ts": "javascript",
    ".tsx": "javascript", ".mts": "javascript", ".cts": "javascript", ".map": "sourcemap",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".bat": "shell", ".cmd": "shell", ".ps1": "shell",
    ".json": "json", ".md": "doc", ".rst": "doc", ".txt": "doc", ".html": "doc", ".css": "doc",
    ".cfg": "config", ".toml": "config", ".ini": "config", ".yml": "config", ".yaml": "config", ".in": "config",
    ".so": "native", ".dll": "native", ".dylib": "native", ".pyd": "native", ".node": "native", ".exe": "native",
    ".png": "asset", ".jpg": "asset", ".jpeg": "asset", ".gif": "asset", ".svg": "asset", ".ico": "asset", ".woff": "asset", ".woff2": "asset",
}
CODE_KINDS = {"python", "javascript", "shell", "pth"}
EXEC_MAGIC = (b"\x7fELF", b"MZ", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe")


def file_kind(rel: str, head: bytes = b"") -> str:
    name = rel.split("/")[-1]
    suffix = Path(name).suffix.lower()
    if head.startswith(EXEC_MAGIC) and suffix not in (".pyc", ".pyo"):
        return "native"
    if suffix in EXT_KIND:
        return EXT_KIND[suffix]
    if name in ("PKG-INFO", "METADATA", "RECORD", "WHEEL") or name.startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS", "CHANGELOG", "README")):
        return "metadata" if name.isupper() and "." not in name and not name.startswith(("LICENSE", "README")) else "doc"
    if head.startswith(b"#!"):
        return "shell" if b"python" not in head[:80] and b"node" not in head[:80] else ("python" if b"python" in head[:80] else "javascript")
    if b"\x00" in head:
        return "binary"
    return "text"


def read_head(path: Path, n: int = 4096) -> bytes:
    with open(path, "rb") as fh:
        return fh.read(n)


def read_text(path: Path, max_bytes: int) -> str | None:
    if path.stat().st_size > max_bytes:
        return None
    data = path.read_bytes()
    if b"\x00" in data[:8192]:
        return None
    return data.decode("utf-8", "replace")
