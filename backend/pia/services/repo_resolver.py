"""Repository discovery, tag resolution and safe source retrieval (no clone, no hooks)."""
import difflib
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .archive import ArchiveError, SafeArchiveInspector, single_top_dir
from .http import HttpError

GITHUB_RE = re.compile(r"github\.com[/:]+([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", re.I)
SAFE_REF = re.compile(r"^[A-Za-z0-9._/@+-]{1,200}$")


class RepoUnavailable(Exception):
    pass


@dataclass
class RepoRef:
    owner: str
    name: str

    @property
    def url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}"


def parse_github_url(url: str | None) -> RepoRef | None:
    if not url:
        return None
    url = url.strip()
    short = re.fullmatch(r"(?:github:)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", url)
    m = short or GITHUB_RE.search(url)
    if not m:
        return None
    name = re.sub(r"\.git$", "", m.group(2))
    if not name or name in (".", ".."):
        return None
    return RepoRef(owner=m.group(1), name=name)


@dataclass
class SourceResolution:
    status: str  # matched | missing | mismatched | no_repo | unreachable
    repo: str | None = None
    ref: str | None = None
    ref_type: str | None = None  # tag | commit | branch | local
    tag: str | None = None
    commit: str | None = None
    expected_commit: str | None = None
    subdir: str | None = None
    candidates: list = field(default_factory=list)
    nearby_tags: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    local: bool = False

    @property
    def comparable(self) -> bool:
        return self.ref is not None

    @property
    def is_fallback(self) -> bool:
        return self.ref_type == "branch"

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(comparable=self.comparable, is_fallback=self.is_fallback)
        return d


def match_tag(tags: dict, version: str, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in tags:
            return c
    pattern = re.compile(r"(?:[\w.-]*?[-@/_])?v?" + re.escape(version))
    for t in sorted(tags):
        if pattern.fullmatch(t):
            return t
    return None


def resolve_against_tags(tags: dict, version, candidates, repo_url, expected_commit=None, subdir=None, fallback_ref="HEAD") -> SourceResolution:
    tag = match_tag(tags, version, candidates)
    base = dict(repo=repo_url, candidates=candidates, expected_commit=expected_commit, subdir=subdir)
    if tag:
        commit = tags[tag]
        res = SourceResolution(status="matched", ref=tag, ref_type="tag", tag=tag, commit=commit, **base)
        if expected_commit and commit and not (commit.startswith(expected_commit[:12]) or expected_commit.startswith(commit[:12])):
            res.status = "mismatched"
            res.notes.append(f"Tag {tag} points to {commit[:12]} but the registry recorded commit {expected_commit[:12]}")
        return res
    nearby = difflib.get_close_matches(version, list(tags), n=6, cutoff=0.4)
    if expected_commit:
        return SourceResolution(status="missing", ref=expected_commit, ref_type="commit", commit=expected_commit, nearby_tags=nearby,
                                notes=["No matching release tag; using the commit recorded by the registry"], **base)
    return SourceResolution(status="missing", ref=fallback_ref, ref_type="branch", nearby_tags=nearby,
                            notes=["No matching release tag; compared against the default-branch snapshot, so differences may be legitimate"], **base)


class RepositoryResolver:
    def __init__(self, http, settings):
        self.http = http
        self.s = settings
        repo_limits = settings.with_limits(max_files=max(settings.limits.max_files, 40000)).limits
        self.inspector = SafeArchiveInspector(repo_limits)

    def list_tags(self, repo: RepoRef) -> dict:
        env = {"PATH": os.environ.get("PATH", ""), "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/true",
               "GIT_CONFIG_NOSYSTEM": "1", "HOME": "/nonexistent"}
        cmd = ["git", "-c", "protocol.allow=never", "-c", "protocol.https.allow=always", "ls-remote", "--tags", repo.url]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.s.limits.git_timeout, env=env, check=False)
        except FileNotFoundError:
            return self._tags_via_api(repo)
        except subprocess.TimeoutExpired as e:
            raise RepoUnavailable(f"git ls-remote timed out for {repo.url}") from e
        if proc.returncode != 0:
            raise RepoUnavailable(f"repository unreachable ({proc.stderr.strip()[:200] or 'git error'})")
        tags, peeled = {}, {}
        for line in proc.stdout.splitlines():
            if "\t" not in line:
                continue
            sha, ref = line.split("\t", 1)
            name = ref.removeprefix("refs/tags/")
            if name.endswith("^{}"):
                peeled[name[:-3]] = sha
            else:
                tags[name] = sha
        tags.update(peeled)
        return tags

    def _tags_via_api(self, repo: RepoRef) -> dict:
        tags = {}
        try:
            for page in range(1, 4):
                data = self.http.get_json(f"https://api.github.com/repos/{repo.owner}/{repo.name}/tags?per_page=100&page={page}")
                for t in data:
                    tags[t["name"]] = t["commit"]["sha"]
                if len(data) < 100:
                    break
        except HttpError as e:
            raise RepoUnavailable(str(e)) from e
        return tags

    def resolve(self, repo_urls: list[str], version: str, candidates: list[str], expected_commit=None, subdir=None) -> SourceResolution:
        repo = next((r for r in (parse_github_url(u) for u in repo_urls) if r), None)
        if repo is None:
            return SourceResolution(status="no_repo", candidates=candidates,
                                    notes=["Package metadata does not declare a recognised GitHub source repository"])
        try:
            tags = self.list_tags(repo)
        except RepoUnavailable as e:
            return SourceResolution(status="unreachable", repo=repo.url, candidates=candidates, notes=[str(e)])
        return resolve_against_tags(tags, version, candidates, repo.url, expected_commit, subdir)

    def fetch(self, res: SourceResolution, dest: Path) -> Path:
        repo = parse_github_url(res.repo)
        if not repo or not res.ref or not SAFE_REF.match(res.ref):
            raise RepoUnavailable("no safe reference to fetch")
        dest.mkdir(parents=True, exist_ok=True)
        archive = dest / "source.tar.gz"
        url = f"https://codeload.github.com/{repo.owner}/{repo.name}/tar.gz/{res.ref}"
        try:
            self.http.download(url, archive, self.s.limits.max_repo_download_bytes)
            report = self.inspector.extract(archive, dest / "src", "source.tar.gz")
        except (HttpError, ArchiveError) as e:
            raise RepoUnavailable(f"could not retrieve source snapshot: {e}") from e
        finally:
            archive.unlink(missing_ok=True)
        root = single_top_dir(report.root, report.files)
        if res.subdir:
            sub = (root / res.subdir).resolve()
            if sub.is_dir() and sub.is_relative_to(root.resolve()):
                root = sub
        return root
