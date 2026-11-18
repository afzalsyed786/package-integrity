import base64
import json
import re

from ..services.http import NotFound
from .base import AnalysisInputError, EcosystemAdapter, ReleaseInfo

NAME_RE = re.compile(r"^(@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*$", re.I)
INSTALL_SCRIPTS = ("preinstall", "install", "postinstall")


def _load_pkg(root):
    pj = root / "package.json" if root else None
    if not pj or not pj.is_file():
        return {}
    try:
        data = json.loads(pj.read_text("utf-8", "replace"))
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


class NpmAdapter(EcosystemAdapter):
    name = "npm"
    label = "npm"
    base = "https://registry.npmjs.org"

    def _enc(self, name):
        if not NAME_RE.match(name or ""):
            raise AnalysisInputError(f"invalid npm package name: {name!r}")
        return name.replace("/", "%2f")

    def _doc(self, name):
        try:
            return self.http.get_json(f"{self.base}/{self._enc(name)}", ttl=120)
        except NotFound as e:
            raise AnalysisInputError(f"npm package {name!r} not found") from e

    def resolve_release(self, name, version=None) -> ReleaseInfo:
        version = version or self._doc(name)["dist-tags"]["latest"]
        try:
            d = self.http.get_json(f"{self.base}/{self._enc(name)}/{version}")
        except NotFound as e:
            raise AnalysisInputError(f"npm release {name}@{version} not found") from e
        dist = d.get("dist", {})
        hashes = {}
        integrity = dist.get("integrity") or ""
        if integrity.startswith("sha512-"):
            hashes["sha512"] = base64.b64decode(integrity[7:]).hex()
        if dist.get("shasum"):
            hashes["sha1"] = dist["shasum"]
        repo = d.get("repository")
        repo_url = repo.get("url") if isinstance(repo, dict) else repo
        subdir = repo.get("directory") if isinstance(repo, dict) else None
        urls = [u for u in (repo_url, d.get("homepage"), (d.get("bugs") or {}).get("url") if isinstance(d.get("bugs"), dict) else None) if u]
        return ReleaseInfo(
            ecosystem="npm", name=d["name"], version=d["version"], artifact_url=dist["tarball"],
            filename=f"{d['name'].split('/')[-1]}-{d['version']}.tgz", artifact_kind="npm-tarball",
            expected_hashes=hashes, repo_urls=urls, expected_commit=d.get("gitHead"), repo_subdir=subdir,
            metadata={"description": d.get("description"), "license": d.get("license"), "scripts": d.get("scripts") or {},
                      "dependencies": d.get("dependencies") or {}, "has_install_script": d.get("hasInstallScript", False)},
        )

    def latest_version(self, name):
        return self._doc(name)["dist-tags"]["latest"]

    def list_versions(self, name):
        d = self._doc(name)
        times = d.get("time", {})
        out = [{"version": v, "published_at": times.get(v), "prerelease": "-" in v, "yanked": False} for v in d.get("versions", {})]
        out.sort(key=lambda x: x["published_at"] or "")
        return out

    def tag_candidates(self, name, version):
        short = name.split("/")[-1]
        return [f"v{version}", version, f"{name}@{version}", f"{short}@{version}", f"{short}-v{version}", f"{short}-{version}"]

    def normalize_for_compare(self, rel_path, text):
        if rel_path != "package.json":
            return text
        try:
            data = json.loads(text)
        except ValueError:
            return text
        if isinstance(data, dict):
            data = {k: v for k, v in data.items() if not k.startswith("_") and k != "gitHead"}
        return json.dumps(data, sort_keys=True, indent=2)

    def install_hooks(self, root):
        pkg = _load_pkg(root)
        scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
        hooks = [{"kind": f"npm_{k}", "file": "package.json", "line": None, "detail": f"{k}: {scripts[k]}", "command": str(scripts[k])}
                 for k in INSTALL_SCRIPTS if k in scripts]
        if root and (root / "binding.gyp").is_file() and not any(k in scripts for k in ("install", "preinstall")):
            hooks.append({"kind": "npm_implicit_gyp", "file": "binding.gyp", "line": None,
                          "detail": "binding.gyp triggers an implicit 'node-gyp rebuild' install script", "command": "node-gyp rebuild"})
        return hooks

    def entry_points(self, root):
        pkg = _load_pkg(root)
        eps = set()
        for key in ("main", "module", "browser"):
            if isinstance(pkg.get(key), str):
                eps.add(pkg[key].lstrip("./"))
        bins = pkg.get("bin")
        if isinstance(bins, str):
            eps.add(bins.lstrip("./"))
        elif isinstance(bins, dict):
            eps |= {str(v).lstrip("./") for v in bins.values()}
        for hook in self.install_hooks(root):
            eps |= {m.lstrip("./") for m in re.findall(r"[\w./-]+\.(?:c|m)?js", hook.get("command", ""))}
        eps.add("index.js")
        return eps

    def declared_outputs(self, root) -> list[str]:
        pkg = _load_pkg(root)
        files = pkg.get("files") if isinstance(pkg.get("files"), list) else []
        return [str(f).lstrip("./").rstrip("/") for f in files]
