"""PIA API regression tests: health/stats/samples, analyses jobs, files, AI explain, watchlist/releases/alerts."""
import os
import time
import urllib.parse

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


def run_job(s, payload, timeout=120):
    r = s.post(f"{API}/analyses", json=payload)
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["status"] == "running"
    jid = job["id"]
    end = time.time() + timeout
    while time.time() < end:
        j = s.get(f"{API}/jobs/{jid}").json()
        if j["status"] != "running":
            return j
        time.sleep(1.5)
    pytest.fail(f"job {jid} timeout: {j}")


# --- Basic endpoints
class TestBasics:
    def test_health(self, s):
        d = s.get(f"{API}/health").json()
        assert d["status"] == "ok"
        assert len(d["detectors"]) == 14
        assert d["ai"]["configured"] is False

    def test_stats(self, s):
        d = s.get(f"{API}/stats").json()
        for k in ["total_analyses", "verdicts", "severities", "risk_trend", "watch_count", "unread_alerts", "recent"]:
            assert k in d

    def test_samples(self, s):
        d = s.get(f"{API}/samples").json()
        assert len(d["synthetic"]) == 3
        assert len(d["real"]) >= 3
        assert all("SYNTHETIC" in x["label"] for x in d["synthetic"])

    def test_analyses_list_no_mongo_id(self, s):
        d = s.get(f"{API}/analyses?limit=5").json()
        assert isinstance(d, list) and d
        assert "_id" not in d[0]

    def test_analysis_404(self, s):
        assert s.get(f"{API}/analyses/doesnotexist").status_code == 404

    def test_job_404(self, s):
        assert s.get(f"{API}/jobs/nope").status_code == 404

    def test_invalid_ecosystem_422(self, s):
        assert s.post(f"{API}/analyses", json={"ecosystem": "maven", "name": "x"}).status_code == 422


# --- Synthetic analyses + file detail + AI explain
@pytest.mark.parametrize("name", ["colorfmt-synth", "tinyhttp-synth", "left-trim-synth"])
def test_synthetic_suspicious(s, name):
    j = run_job(s, {"ecosystem": "synthetic", "name": name})
    assert j["status"] == "completed", j
    assert j["verdict"] == "Suspicious"
    doc = s.get(f"{API}/analyses/{j['analysis_id']}").json()
    assert doc["package"] == name and doc["verdict"] == "Suspicious"
    assert doc["findings"] and doc["files"]
    for f in doc["files"]:
        if f.get("has_detail"):
            r = s.get(f"{API}/analyses/{doc['id']}/files/{f['id']}")
            assert r.status_code == 200, f
            body = r.json()
            assert isinstance(body, dict) and body
    # AI
    r = s.post(f"{API}/analyses/{doc['id']}/explain")
    assert r.status_code == 200
    assert r.json()["status"] == "disabled"
    doc2 = s.get(f"{API}/analyses/{doc['id']}").json()
    assert doc2["ai_explanation"] and doc2["ai_explanation"]["status"] == "disabled"
    p = s.get(f"{API}/analyses/{doc['id']}/explain/preview")
    assert p.status_code == 200 and p.json()


def test_left_trim_rejected_entries(s):
    j = run_job(s, {"ecosystem": "synthetic", "name": "left-trim-synth"})
    doc = s.get(f"{API}/analyses/{j['analysis_id']}").json()
    archive = doc.get("archive") or {}
    assert str(archive).lower().count("traversal") or str(archive).lower().count("rejected"), archive


def test_file_detail_404(s):
    d = s.get(f"{API}/analyses?limit=1").json()[0]
    assert s.get(f"{API}/analyses/{d['id']}/files/nofile").status_code == 404


# --- Real packages (network)
@pytest.mark.parametrize("eco,name,ver", [("pypi", "six", "1.17.0"), ("npm", "ms", "2.1.3")])
def test_real_clean(s, eco, name, ver):
    j = run_job(s, {"ecosystem": eco, "name": name, "version": ver})
    assert j["status"] == "completed", j
    assert j["verdict"] == "Clean"


def test_invalid_package_fails_gracefully(s):
    j = run_job(s, {"ecosystem": "pypi", "name": "this-package-does-not-exist-xyz123"}, timeout=60)
    assert j["status"] == "failed"
    assert j.get("error")


# --- Watchlist / releases / alerts
class TestWatch:
    wid = "npm:ms"

    def test_watch_flow(self, s):
        q = urllib.parse.quote(self.wid, safe="")
        existing = [w["id"] for w in s.get(f"{API}/watchlist").json()]
        if self.wid in existing:
            pytest.skip("npm:ms already watched (user data) - not touching")
        try:
            r = s.post(f"{API}/watchlist", json={"ecosystem": "npm", "name": "ms", "interval_minutes": 60})
            assert r.status_code == 200, r.text
            item = r.json()
            assert item["id"] == self.wid and item["latest_version"]
            latest = item["latest_version"]
            assert s.post(f"{API}/watchlist", json={"ecosystem": "npm", "name": "ms", "interval_minutes": 60}).status_code == 409
            assert self.wid in [w["id"] for w in s.get(f"{API}/watchlist").json()]
            assert s.post(f"{API}/watchlist/{q}/check").status_code == 200
            time.sleep(3)
            r = s.post(f"{API}/watchlist/{q}/rewind")
            assert r.status_code == 200 and r.json()["rediscovering"] == latest
            rel = None
            for _ in range(30):
                time.sleep(2)
                rels = s.get(f"{API}/releases", params={"ecosystem": "npm", "name": "ms"}).json()
                rel = next((x for x in rels if x["version"] == latest), None)
                if rel and rel.get("status") == "analyzed":
                    break
            assert rel and rel["status"] == "analyzed", rel
            assert rel.get("verdict") in ("Clean", "Suspicious", "Inconclusive")
            alerts = s.get(f"{API}/alerts").json()
            assert any(a.get("name") == "ms" for a in alerts)
            assert s.post(f"{API}/alerts/read-all").status_code == 200
            assert s.get(f"{API}/alerts", params={"unread_only": True}).json() == []
        finally:
            assert s.delete(f"{API}/watchlist/{q}").status_code == 200
        assert self.wid not in [w["id"] for w in s.get(f"{API}/watchlist").json()]

    def test_watch_unknown_package(self, s):
        r = s.post(f"{API}/watchlist", json={"ecosystem": "pypi", "name": "this-package-does-not-exist-xyz123"})
        assert r.status_code == 404

    def test_check_unknown_watch(self, s):
        assert s.post(f"{API}/watchlist/{urllib.parse.quote('npm:nope-xyz', safe='')}/check").status_code == 404
