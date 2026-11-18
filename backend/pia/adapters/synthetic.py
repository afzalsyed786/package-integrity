"""Synthetic lab adapter: builds clearly-labelled, inert tampered samples from sample_data/ at analysis time."""
import base64
import importlib.util
import io
import json
import marshal
import sys
import tarfile
import time
from pathlib import Path

from ..services.http import hash_file
from .base import AnalysisInputError, EcosystemAdapter, ReleaseInfo


def _vlq(value: int) -> str:
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    v = (-value << 1) | 1 if value < 0 else value << 1
    out = ""
    while True:
        digit = v & 31
        v >>= 5
        out += chars[digit | (32 if v else 0)]
        if not v:
            return out


def build_bundle(source_text: str, source_name: str, injected: str, map_name: str) -> tuple[str, str]:
    """Identity-mapped bundle; injected lines are deliberately left unmapped."""
    src_lines = source_text.splitlines()
    segs = ["AAAA"] + [_vlq(0) + _vlq(0) + _vlq(1) + _vlq(0)] * (len(src_lines) - 1)
    inj_lines = injected.splitlines()
    bundle = "\n".join(src_lines + inj_lines + [f"//# sourceMappingURL={map_name}"]) + "\n"
    smap = {"version": 3, "file": map_name.removesuffix(".map"), "sources": [source_name],
            "sourcesContent": [source_text], "names": [], "mappings": ";".join(segs + [""] * len(inj_lines))}
    return bundle, json.dumps(smap)


def _tree(root: Path) -> dict[str, bytes]:
    """Read a sample tree; '.sample' suffixes keep package.json files inert for local tooling."""
    return {p.relative_to(root).as_posix().removesuffix(".sample"): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class SyntheticAdapter(EcosystemAdapter):
    name = "synthetic"
    label = "Synthetic lab"

    def __init__(self, http, settings, delegates: dict):
        super().__init__(http, settings)
        self.delegates = delegates
        self.root = settings.samples_dir / "synthetic"

    def samples(self) -> list[dict]:
        out = []
        for m in sorted(self.root.glob("*/manifest.json")):
            data = json.loads(m.read_text())
            out.append({k: data[k] for k in ("package", "version", "style", "title", "label", "description", "techniques")})
        return out

    def _manifest(self, name):
        for m in self.root.glob("*/manifest.json"):
            data = json.loads(m.read_text())
            if data["package"] == name:
                return m.parent, data
        raise AnalysisInputError(f"unknown synthetic sample {name!r}")

    def resolve_release(self, name, version=None):
        folder, m = self._manifest(name)
        if version and version != m["version"]:
            raise AnalysisInputError(f"synthetic sample {name} only provides version {m['version']}")
        ext = ".tgz" if m["style"] == "npm" else ".tar.gz"
        return ReleaseInfo(
            ecosystem="synthetic", name=m["package"], version=m["version"], artifact_url=f"sample://{m['package']}",
            filename=f"{m['package']}-{m['version']}{ext}", artifact_kind="npm-tarball" if m["style"] == "npm" else "sdist",
            repo_urls=[m.get("repository", "")], local_source=folder / "repo", local_tags=m.get("tags", {}), synthetic=True,
            metadata={"synthetic": True, "label": m["label"], "title": m["title"], "style": m["style"],
                      "description": m["description"], "techniques": m["techniques"]},
        )

    def list_versions(self, name):
        _, m = self._manifest(name)
        return [{"version": m["version"], "published_at": None, "prerelease": False, "yanked": False}]

    def profile(self, release):
        return self.delegates[release.metadata["style"]]

    def materialize_source(self, release, dest: Path) -> Path:
        for rel, data in _tree(release.local_source).items():
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return dest

    def download(self, release, dest_dir):
        folder, m = self._manifest(release.name)
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / release.filename
        prefix = "package" if m["style"] == "npm" else f"{m['package']}-{m['version']}"
        files = _tree(folder / "package")
        for b in m.get("bundles", []):
            src = (folder / "repo" / b["source"]).read_text()
            inj = (folder / b["inject"]).read_text()
            bundle, smap = build_bundle(src, b["map_source"], inj, Path(b["out"]).name + ".map")
            files[b["out"]] = bundle.encode()
            files[b["out"] + ".map"] = smap.encode()
        for c in m.get("compiled", []):
            src = (folder / c["source"]).read_text()
            code = compile(src, c["filename"], "exec")  # compile only, never executed
            header = importlib.util.MAGIC_NUMBER + b"\x00\x00\x00\x00" + int(time.time()).to_bytes(4, "little") + len(src).to_bytes(4, "little")
            out_rel = c["out"].replace("{tag}", sys.implementation.cache_tag)
            files[out_rel] = header + marshal.dumps(code)
        with tarfile.open(out, "w:gz") as tf:
            for rel, data in sorted(files.items()):
                info = tarfile.TarInfo(f"{prefix}/{rel}")
                info.size, info.mode, info.mtime = len(data), 0o644, 1700000000
                tf.addfile(info, io.BytesIO(data))
            for inj in m.get("archive_injections", []):
                info = tarfile.TarInfo(inj["name"] if inj["type"] == "traversal" else f"{prefix}/{inj['name']}")
                info.mtime = 1700000000
                if inj["type"] == "symlink":
                    info.type, info.linkname = tarfile.SYMTYPE, inj["target"]
                    tf.addfile(info)
                else:
                    data = base64.b64decode(inj["content_b64"]) if "content_b64" in inj else inj.get("content", "").encode()
                    info.size = len(data)
                    tf.addfile(info, io.BytesIO(data))
        return out, hash_file(out)
