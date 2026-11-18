"""Storage abstraction: backends implement document primitives; domain operations live here."""
from abc import ABC, abstractmethod
from datetime import datetime, timezone

SUMMARY_FIELDS = ["id", "created_at", "ecosystem", "package", "version", "verdict", "risk_score", "synthetic", "severity_counts",
                  "category_counts", "summary", "duration_ms", "source", "artifact", "verdict_reasons", "coverage", "metadata"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store(ABC):
    @abstractmethod
    def _upsert(self, coll: str, doc: dict) -> None: ...

    @abstractmethod
    def _insert_if_absent(self, coll: str, doc: dict) -> bool: ...

    @abstractmethod
    def _get(self, coll: str, doc_id: str) -> dict | None: ...

    @abstractmethod
    def _find(self, coll: str, filters: dict | None = None, sort: str = "created_at", desc: bool = True,
              limit: int = 100, fields: list[str] | None = None) -> list[dict]: ...

    @abstractmethod
    def _update(self, coll: str, doc_id: str, fields: dict) -> None: ...

    @abstractmethod
    def _delete(self, coll: str, filters: dict) -> int: ...

    def save_analysis(self, result: dict, details: dict) -> None:
        self._upsert("analyses", result)
        for fid, payload in details.items():
            self._upsert("file_details", {"id": f"{result['id']}:{fid}", "analysis_id": result["id"], "file_id": fid,
                                          "payload": payload, "created_at": result["created_at"]})

    def get_analysis(self, analysis_id: str) -> dict | None:
        return self._get("analyses", analysis_id)

    def get_file_detail(self, analysis_id: str, file_id: str) -> dict | None:
        doc = self._get("file_details", f"{analysis_id}:{file_id}")
        return doc["payload"] if doc else None

    def list_analyses(self, limit: int = 50, **filters) -> list[dict]:
        return self._find("analyses", {k: v for k, v in filters.items() if v not in (None, "")}, limit=limit, fields=SUMMARY_FIELDS)

    def set_ai_explanation(self, analysis_id: str, explanation: dict) -> None:
        self._update("analyses", analysis_id, {"ai_explanation": explanation})

    def add_watch(self, item: dict) -> bool:
        return self._insert_if_absent("watchlist", item)

    def list_watch(self) -> list[dict]:
        return self._find("watchlist", limit=500)

    def get_watch(self, watch_id: str) -> dict | None:
        return self._get("watchlist", watch_id)

    def update_watch(self, watch_id: str, fields: dict) -> None:
        self._update("watchlist", watch_id, fields)

    def delete_watch(self, watch_id: str) -> None:
        item = self.get_watch(watch_id)
        self._delete("watchlist", {"id": watch_id})
        if item:
            self._delete("releases", {"ecosystem": item["ecosystem"], "name": item["name"]})

    def record_release(self, doc: dict) -> bool:
        doc.setdefault("created_at", now_iso())
        doc["id"] = f"{doc['ecosystem']}:{doc['name']}:{doc['version']}"
        return self._insert_if_absent("releases", doc)

    def update_release(self, release_id: str, fields: dict) -> None:
        self._update("releases", release_id, fields)

    def delete_release(self, release_id: str) -> None:
        self._delete("releases", {"id": release_id})

    def list_releases(self, ecosystem=None, name=None, limit: int = 200) -> list[dict]:
        filters = {k: v for k, v in {"ecosystem": ecosystem, "name": name}.items() if v}
        return self._find("releases", filters, sort="published_at", limit=limit)

    def add_alert(self, alert: dict) -> None:
        from ..engine.models import new_id

        alert.setdefault("id", new_id())
        alert.setdefault("created_at", now_iso())
        alert.setdefault("read", False)
        self._upsert("alerts", alert)

    def list_alerts(self, limit: int = 100, unread_only: bool = False) -> list[dict]:
        return self._find("alerts", {"read": False} if unread_only else None, limit=limit)

    def mark_alert_read(self, alert_id: str) -> None:
        self._update("alerts", alert_id, {"read": True})

    def mark_all_alerts_read(self) -> None:
        for a in self.list_alerts(limit=1000, unread_only=True):
            self.mark_alert_read(a["id"])

    def stats(self) -> dict:
        analyses = self.list_analyses(limit=1000)
        verdicts = {"Clean": 0, "Suspicious": 0, "Inconclusive": 0}
        severities, categories = {}, {}
        for a in analyses:
            verdicts[a["verdict"]] = verdicts.get(a["verdict"], 0) + 1
            for k, v in (a.get("severity_counts") or {}).items():
                severities[k] = severities.get(k, 0) + v
            for k, v in (a.get("category_counts") or {}).items():
                categories[k] = categories.get(k, 0) + v
        trend = [{"label": f"{a['package']}@{a['version']}", "risk": a["risk_score"], "verdict": a["verdict"], "created_at": a["created_at"]}
                 for a in reversed(analyses[:20])]
        return {"total_analyses": len(analyses), "verdicts": verdicts, "severities": severities, "categories": categories,
                "risk_trend": trend, "watch_count": len(self.list_watch()),
                "unread_alerts": len(self.list_alerts(limit=1000, unread_only=True)), "recent": analyses[:8]}
