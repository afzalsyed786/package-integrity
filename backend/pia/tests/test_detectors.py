"""Unit tests for individual detectors using hand-built contexts (no network)."""
from pathlib import Path
from types import SimpleNamespace

from pia.adapters.npm import NpmAdapter
from pia.adapters.pypi import PyPIAdapter
from pia.detectors import AnalysisContext, FileContext
from pia.detectors.code_behavior import DynamicExecDetector, NetworkDetector
from pia.detectors.install_hooks import InstallHookDetector
from pia.detectors.payloads import EncodedPayloadDetector, ObfuscationDetector
from pia.detectors.provenance import ProvenanceDetector
from pia.engine.comparison import added_lines
from pia.engine.models import FileRecord
from pia.services.archive import ExtractionReport
from pia.services.repo_resolver import SourceResolution, parse_github_url, resolve_against_tags


def fctx(path, text, repo_text=None, status="package_only", kind="python", entry=False):
    rec = FileRecord(path=path, status=status, kind=kind)
    added = added_lines(repo_text, text) if repo_text is not None else None
    return FileContext(record=rec, abs_path=Path("/nonexistent"), text=text, repo_text=repo_text, added=added, is_entry=entry)


def ctx(files, baseline=None, hooks=None, repo_hooks=None, source=None):
    return AnalysisContext(release=SimpleNamespace(version="1.2.0", repo_urls=[]), source=source or SourceResolution(status="matched", ref="v1"), profile=None, files=files,
                           records=[f.record for f in files], pkg_root=Path("."), repo_root=None, pkg_map={}, repo_map={},
                           archive_report=ExtractionReport(root=Path("."), archive_type="tar.gz"), hooks=hooks or [],
                           repo_hooks=repo_hooks or [], baseline=baseline or {})


def test_exec_of_decoded_data_is_critical():
    f = fctx("pkg/x.py", "import base64 as b\nexec(b.b64decode(payload))\n")
    out = DynamicExecDetector().run(ctx([f]))
    assert out[0].severity == "critical" and "base64.b64decode" in out[0].reason


def test_literal_eval_is_low_and_baseline_eval_ignored():
    f = fctx("pkg/x.py", "eval('1+1')\n")
    assert DynamicExecDetector().run(ctx([f]))[0].severity == "low"
    old = "def m(e):\n    return eval(e, {}, {})\n"
    unchanged = fctx("pkg/m.py", old + "X = 1\n", repo_text=old, status="modified")
    assert DynamicExecDetector().run(ctx([unchanged])) == []


def test_network_baseline_downgrades_severity():
    f = fctx("pkg/c.py", "import requests\nrequests.get(url)\n")
    plain = NetworkDetector().run(ctx([f]))[0].severity
    base = NetworkDetector().run(ctx([f], baseline={"network": 3}))[0].severity
    assert plain == "medium" and base == "low"


def test_network_at_import_time_is_upgraded():
    f = fctx("pkg/__init__.py", "import urllib.request\nurllib.request.urlopen('https://x.example.invalid')\n", entry=True)
    out = NetworkDetector().run(ctx([f]))[0]
    assert out.severity == "high" and "x.example.invalid" in out.reason


def test_base64_data_uri_and_random_blob_not_flagged():
    data_uri = 'ICON = "data:image/png;base64,' + "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8" * 3 + '"\n'
    assert EncodedPayloadDetector().run(ctx([fctx("pkg/icon.py", data_uri)])) == []


def test_base64_code_payload_flagged():
    import base64
    blob = base64.b64encode(b"import os, subprocess\nsubprocess.call(['/bin/sh','-c','id'])\n" * 2).decode()
    out = EncodedPayloadDetector().run(ctx([fctx("pkg/p.py", f'P = "{blob}"\n')]))
    assert out and out[0].severity == "high" and "subprocess" in out[0].reason


def test_obfuscation_detected_but_plain_code_clean():
    obf = "_k = ''.join(chr(c) for c in [101,120,101,99])\nf = getattr(__builtins__, _k)\n"
    assert ObfuscationDetector().run(ctx([fctx("pkg/o.py", obf)]))[0].category == "obfuscation"
    plain = "def add(a, b):\n    return a + b\n"
    assert ObfuscationDetector().run(ctx([fctx("pkg/p.py", plain)])) == []


def test_js_obfuscator_identifiers():
    js = "var _0x1a2b=['a'];var _0x3c4d=_0x1a2b;function _0x5e6f(){return _0x3c4d}_0x5e6f();var _0xabcd=1;\n"
    out = ObfuscationDetector().run(ctx([fctx("dist/a.js", js, kind="javascript")]))
    assert out and "_0x" in out[0].reason


def test_new_install_hook_flagged_but_baseline_hook_info(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"postinstall": "node setup.js"}}')
    hooks = NpmAdapter(None, None).install_hooks(tmp_path)
    f = fctx("setup.js", "console.log(1)\n", kind="javascript")
    new = InstallHookDetector().run(ctx([f], hooks=hooks))
    assert new[0].severity == "critical"
    same = InstallHookDetector().run(ctx([f], hooks=hooks, repo_hooks=hooks))
    assert same[0].severity == "info"


def test_setup_py_cmdclass_detected(tmp_path):
    (tmp_path / "setup.py").write_text("from setuptools.command.install import install\nclass X(install):\n    pass\nsetup(cmdclass={'install': X})\n")
    kinds = {h["kind"] for h in PyPIAdapter(None, None).install_hooks(tmp_path)}
    assert kinds == {"setup_cmdclass", "setup_cmdclass_kw"}


def test_missing_tag_resolution_and_finding():
    tags = {"v1.0.0": "a" * 40, "v1.1.0": "b" * 40}
    res = resolve_against_tags(tags, "1.2.0", ["v1.2.0", "1.2.0"], "https://github.com/o/r")
    assert res.status == "missing" and res.is_fallback
    out = ProvenanceDetector().run(ctx([], source=res))
    assert out[0].title == "Missing release tag"


def test_tag_matching_variants_and_commit_mismatch():
    tags = {"pkg-v2.0.0": "c" * 40}
    res = resolve_against_tags(tags, "2.0.0", ["v2.0.0"], "https://github.com/o/r", expected_commit="d" * 40)
    assert res.tag == "pkg-v2.0.0" and res.status == "mismatched"


def test_github_url_parsing():
    assert parse_github_url("git+https://github.com/vercel/ms.git").url == "https://github.com/vercel/ms"
    assert parse_github_url("github:user/repo").name == "repo"
    assert parse_github_url("https://github.com/a/b/tree/main/packages/x").name == "b"
    assert parse_github_url("https://gitlab.com/a/b") is None
