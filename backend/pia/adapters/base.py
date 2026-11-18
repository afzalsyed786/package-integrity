"""Ecosystem adapter contract. New ecosystems implement this; the core engine stays unchanged."""
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..services.archive import single_top_dir
from ..services.http import hash_file


class AnalysisInputError(Exception):
    pass


@dataclass
class ReleaseInfo:
    ecosystem: str
    name: str
    version: str
    artifact_url: str
    filename: str
    artifact_kind: str
    expected_hashes: dict = field(default_factory=dict)
    repo_urls: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    published_at: str | None = None
    expected_commit: str | None = None
    repo_subdir: str | None = None
    local_source: Path | None = None
    local_tags: dict | None = None
    synthetic: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["local_source"] = str(self.local_source) if self.local_source else None
        return d


class EcosystemAdapter(ABC):
    name = "base"
    label = "Base"

    def __init__(self, http, settings):
        self.http = http
        self.s = settings

    @abstractmethod
    def resolve_release(self, name: str, version: str | None = None) -> ReleaseInfo: ...

    @abstractmethod
    def list_versions(self, name: str) -> list[dict]: ...

    def profile(self, release: ReleaseInfo) -> "EcosystemAdapter":
        """Adapter whose build conventions apply to this release."""
        return self

    def download(self, release: ReleaseInfo, dest_dir: Path) -> tuple[Path, dict]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / Path(release.filename).name
        info = self.http.download(release.artifact_url, path, self.s.limits.max_download_bytes)
        return path, info

    def materialize_source(self, release: ReleaseInfo, dest: Path) -> Path:
        return release.local_source

    def package_root(self, root: Path, files: list[str]) -> Path:
        return single_top_dir(root, files)

    def tag_candidates(self, name: str, version: str) -> list[str]:
        short = name.split("/")[-1]
        return [f"v{version}", version, f"{short}-{version}", f"{short}-v{version}", f"{short}@{version}", f"release-{version}"]

    def classify_expected(self, rel_path: str) -> str | None:
        return None

    def normalize_for_compare(self, rel_path: str, text: str) -> str:
        return text

    def install_hooks(self, root: Path | None) -> list[dict]:
        return []

    def build_manifest(self, root: Path) -> dict | None:
        return None

    def entry_points(self, root: Path) -> set[str]:
        return set()

    def source_prefix_hints(self) -> list[str]:
        return ["src/", "lib/"]


def file_digests(path: Path) -> dict:
    return hash_file(path)
