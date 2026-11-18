# Regression tests for iteration 2 (post code-quality refactor): diff skip-row line numbers, watchlist 404s
import os
import time
import urllib.parse
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


@pytest.fixture(scope="module")
def s():
    return requests.Session()


def run_job(s, payload):
    r = s.post(f"{BASE_URL}/api/analyses", json=payload)
    assert r.status_code in (200, 201, 202), r.text
    job_id = r.json().get("job_id") or r.json().get("id")
    for _ in range(90):
        j = s.get(f"{BASE_URL}/api/jobs/{job_id}").json()
        if j.get("status") in ("done", "completed", "failed"):
            return j
        time.sleep(1)
    pytest.fail("job timeout")


# Synthetic analysis -> Suspicious, diff skip rows carry numeric line numbers
def test_tinyhttp_skip_rows_numeric(s):
    j = run_job(s, {"ecosystem": "synthetic", "name": "tinyhttp-synth"})
    assert j["status"] in ("done", "completed"), j
    aid = j["analysis_id"]
    a = s.get(f"{BASE_URL}/api/analyses/{aid}").json()
    assert a["verdict"] == "Suspicious"
    files = a.get("files") or []
    mods = [f for f in files if f.get("has_detail") and f.get("status") == "modified"]
    assert mods, "no modified files"
    found_skip = False
    for f in mods:
        d = s.get(f"{BASE_URL}/api/analyses/{aid}/files/{f['id']}")
        assert d.status_code == 200
        body = d.json()
        diff = body.get("diff") or body
        rows = diff.get("rows", [])
        for row in rows:
            if row[0] == "skip":
                found_skip = True
                assert isinstance(row[1], int) and isinstance(row[3], int), row
        # keys (kind, pkg line, repo line) unique for React
        keys = [(r[0], r[1], r[3]) for r in rows]
        assert len(keys) == len(set(keys)), f"duplicate row keys in {f.get('path')}"
    print("found skip row:", found_skip)


def test_watch_nonexistent_404(s):
    r = s.post(f"{BASE_URL}/api/watchlist", json={"ecosystem": "pypi", "name": "this-package-does-not-exist-xyz123"})
    assert r.status_code == 404, r.text


def test_delete_unknown_watch_404(s):
    r = s.delete(f"{BASE_URL}/api/watchlist/{urllib.parse.quote('pypi:nope-xyz-unknown', safe='')}")
    assert r.status_code == 404, r.text
