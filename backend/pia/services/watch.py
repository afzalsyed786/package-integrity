"""Watch mode: polls registries for new releases, deduplicates, analyses them and raises alerts."""
import logging
import threading
from datetime import datetime, timedelta, timezone

from ..adapters import AnalysisInputError
from ..database.base import now_iso

log = logging.getLogger("pia.watch")
VERDICT_ALERT = {"Suspicious": "critical", "Inconclusive": "warning", "Clean": "info"}


def _now():
    return datetime.now(timezone.utc)


class WatchService:
    def __init__(self, store, analyzer, max_new_per_poll: int = 3):
        self.store = store
        self.analyzer = analyzer
        self.max_new = max_new_per_poll
        self._locks: dict[str, threading.Lock] = {}

    def _adapter(self, ecosystem):
        if ecosystem not in ("pypi", "npm"):
            raise AnalysisInputError("watch mode supports registry ecosystems only (pypi, npm)")
        return self.analyzer.adapters[ecosystem]

    def add(self, ecosystem: str, name: str, interval_minutes: int = 60) -> dict:
        ecosystem, name = ecosystem.lower().strip(), name.strip()
        versions = self._adapter(ecosystem).list_versions(name)
        interval = max(5, min(int(interval_minutes), 1440))
        item = {"id": f"{ecosystem}:{name}", "ecosystem": ecosystem, "name": name, "interval_minutes": interval, "enabled": True,
                "created_at": now_iso(), "last_checked": now_iso(), "next_check": (_now() + timedelta(minutes=interval)).isoformat(),
                "last_error": None, "latest_version": versions[-1]["version"] if versions else None, "known_versions": len(versions),
                "checks": 0, "new_releases": 0}
        if not self.store.add_watch(item):
            raise ValueError(f"{ecosystem}:{name} is already on the watchlist")
        for v in versions:
            self.store.record_release({"ecosystem": ecosystem, "name": name, "version": v["version"], "published_at": v["published_at"],
                                       "status": "baseline", "prerelease": v.get("prerelease", False)})
        self.store.add_alert({"severity": "info", "title": f"Monitoring started for {name}", "ecosystem": ecosystem, "name": name,
                              "message": f"{len(versions)} existing releases recorded as baseline; polling every {interval} min."})
        return item

    def check(self, watch_id: str, analyze: bool = True) -> dict:
        lock = self._locks.setdefault(watch_id, threading.Lock())
        if not lock.acquire(blocking=False):
            return {"skipped": True, "reason": "check already running"}
        try:
            return self._check(watch_id, analyze)
        finally:
            lock.release()

    def _check(self, watch_id, analyze):
        item = self.store.get_watch(watch_id)
        if not item:
            raise KeyError(watch_id)
        eco, name = item["ecosystem"], item["name"]
        try:
            versions = self._adapter(eco).list_versions(name)
        except Exception as e:
            backoff = min(item["interval_minutes"] * 2, 1440)
            self.store.update_watch(watch_id, {"last_error": str(e)[:300], "last_checked": now_iso(),
                                               "next_check": (_now() + timedelta(minutes=backoff)).isoformat()})
            return {"error": str(e)}
        new = []
        for v in versions:
            if v.get("yanked"):
                continue
            if self.store.record_release({"ecosystem": eco, "name": name, "version": v["version"], "published_at": v["published_at"],
                                          "status": "discovered", "discovered_at": now_iso(), "prerelease": v.get("prerelease", False)}):
                new.append(v)
        to_analyze = new[-self.max_new:]
        results = []
        for v in new:
            self.store.add_alert({"severity": "info", "title": f"New release {name} {v['version']}", "ecosystem": eco, "name": name,
                                  "version": v["version"], "message": "Discovered by watch mode" + ("; queued for analysis" if analyze and v in to_analyze else "")})
        if analyze:
            for v in to_analyze:
                results.append(self._analyze(eco, name, v["version"]))
        self.store.update_watch(watch_id, {
            "last_checked": now_iso(), "next_check": (_now() + timedelta(minutes=item["interval_minutes"])).isoformat(), "last_error": None,
            "latest_version": versions[-1]["version"] if versions else item.get("latest_version"), "known_versions": len(versions),
            "checks": item.get("checks", 0) + 1, "new_releases": item.get("new_releases", 0) + len(new)})
        return {"new_versions": [v["version"] for v in new], "analyses": results}

    def _analyze(self, eco, name, version) -> dict:
        rid = f"{eco}:{name}:{version}"
        try:
            res = self.analyzer.analyze(eco, name, version)
        except Exception as e:
            self.store.update_release(rid, {"status": "failed", "error": str(e)[:300]})
            self.store.add_alert({"severity": "warning", "title": f"Analysis failed for {name} {version}", "ecosystem": eco, "name": name,
                                  "version": version, "message": str(e)[:300]})
            return {"version": version, "error": str(e)}
        self.store.update_release(rid, {"status": "analyzed", "analysis_id": res["id"], "verdict": res["verdict"], "risk_score": res["risk_score"]})
        self.store.add_alert({"severity": VERDICT_ALERT[res["verdict"]], "title": f"{name} {version}: {res['verdict']}", "ecosystem": eco,
                              "name": name, "version": version, "analysis_id": res["id"],
                              "message": f"Risk {res['risk_score']}. " + "; ".join(res["verdict_reasons"][:2])})
        return {"version": version, "analysis_id": res["id"], "verdict": res["verdict"]}

    def rewind(self, watch_id: str) -> str | None:
        """Demo helper: forget the newest release so the next check rediscovers and analyses it."""
        item = self.store.get_watch(watch_id)
        if not item or not item.get("latest_version"):
            return None
        self.store.delete_release(f"{item['ecosystem']}:{item['name']}:{item['latest_version']}")
        return item["latest_version"]

    def run_due(self) -> list:
        ran = []
        now = _now().isoformat()
        for item in self.store.list_watch():
            if item.get("enabled") and (item.get("next_check") or "") <= now:
                ran.append((item["id"], self.check(item["id"])))
        return ran

    def run_forever(self, stop: threading.Event, tick: int = 30) -> None:
        while not stop.is_set():
            try:
                self.run_due()
            except Exception:
                log.exception("watch tick failed")
            stop.wait(tick)
