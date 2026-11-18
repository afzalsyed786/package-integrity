"""End-to-end tests over the synthetic lab (no network) plus storage, scoring and watch-mode dedup."""
import pytest

from pia.engine.models import Finding
from pia.engine.scoring import combine, score
from pia.services.redaction import redact
from pia.services.repo_resolver import SourceResolution
from pia.services.watch import WatchService


def rules(result):
    return {f["rule_id"] for f in result["findings"]}


def test_sample_install_hook(analyzer):
    r = analyzer.analyze("synthetic", "colorfmt-synth")
    assert r["verdict"] == "Suspicious" and r["synthetic"]
    assert {"install-hook", "dynamic-exec", "encoded-payload", "correlation"} <= rules(r)
    assert r["source"]["status"] == "matched"
    expected = {f["path"] for f in r["files"] if f["status"] == "expected"}
    assert {"PKG-INFO", "colorfmt/_version.py"} <= expected
    assert all(f["evidence"] for f in r["findings"] if f["severity"] != "info")


def test_sample_obfuscated_import(analyzer):
    r = analyzer.analyze("synthetic", "tinyhttp-synth")
    assert r["verdict"] == "Suspicious"
    assert {"bytecode", "obfuscation", "encoded-payload", "semantic-change", "manifest-integrity", "provenance"} <= rules(r)
    assert r["source"]["status"] == "missing"
    flagged = {f["file"] for f in r["findings"]}
    assert "tinyhttp/utils.py" not in flagged, "baseline eval in source must not be flagged"
    assert "tinyhttp/assets/brand.json" not in flagged, "data URI must not be flagged"


def test_sample_npm_bundle(analyzer):
    r = analyzer.analyze("synthetic", "left-trim-synth")
    assert r["verdict"] == "Suspicious"
    assert {"source-map", "install-hook", "credential-access", "provenance"} <= rules(r)
    kinds = {x["kind"] for x in r["archive"]["rejected"]}
    assert {"path_traversal", "symlink_escape"} <= kinds
    assert any(f["title"] == "Unmapped code in bundle" for f in r["findings"])


def test_results_persisted_with_diffs(analyzer, store):
    r = analyzer.analyze("synthetic", "colorfmt-synth")
    assert store.get_analysis(r["id"])["verdict"] == "Suspicious"
    setup = next(f for f in r["files"] if f["path"] == "setup.py")
    detail = store.get_file_detail(r["id"], setup["id"])
    assert detail["mode"] == "diff" and any(row[0] in ("changed", "pkg_only") for row in detail["rows"])
    assert store.stats()["verdicts"]["Suspicious"] == 1


def test_scoring_clean_vs_inconclusive():
    ok = SourceResolution(status="matched", ref="v1")
    assert score([], [], ok, [])["verdict"] == "Clean"
    assert score([], [], SourceResolution(status="no_repo"), [])["verdict"] == "Inconclusive"
    low = [Finding(rule_id="x", title="t", category="network", severity="low", confidence=0.5, reason="r")]
    assert score(low, [], ok, [])["verdict"] == "Clean"
    assert combine([50, 50]) == 75


def test_redaction_strips_secrets():
    text = 'token = "ghp_abcdefghijklmnopqrstuvwxyz123456" AKIAABCDEFGHIJKLMNOP'
    out = redact(text)
    assert "ghp_" not in out and "AKIA" not in out


class FakeAdapter:
    def __init__(self):
        self.versions = [{"version": "1.0.0", "published_at": "2024-01-01"}]

    def list_versions(self, name):
        return list(self.versions)


class FakeAnalyzer:
    def __init__(self):
        self.adapters = {"pypi": FakeAdapter()}
        self.calls = []

    def analyze(self, eco, name, version):
        self.calls.append(version)
        return {"id": f"a-{version}", "verdict": "Clean", "risk_score": 0, "verdict_reasons": ["ok"]}


def test_watch_mode_dedup_and_alerts(store):
    fa = FakeAnalyzer()
    w = WatchService(store, fa)
    w.add("pypi", "demo", 5)
    assert w.check("pypi:demo")["new_versions"] == []
    fa.adapters["pypi"].versions.append({"version": "1.1.0", "published_at": "2024-02-01"})
    assert w.check("pypi:demo")["new_versions"] == ["1.1.0"]
    assert w.check("pypi:demo")["new_versions"] == []
    assert fa.calls == ["1.1.0"]
    assert any("1.1.0: Clean" in a["title"] for a in store.list_alerts())
    with pytest.raises(ValueError):
        w.add("pypi", "demo")
    assert w.rewind("pypi:demo") == "1.1.0"
    assert w.check("pypi:demo")["new_versions"] == ["1.1.0"]


@pytest.mark.network
def test_real_release_six_is_clean(analyzer):
    r = analyzer.analyze("pypi", "six", "1.17.0")
    assert r["verdict"] == "Clean" and r["source"]["status"] == "matched"
