import json
import re
import sqlite3
import threading

from ..config import get_settings
from .base import Store

IDENT = re.compile(r"^[a-z_]+$")


class SQLiteStore(Store):
    """Local SQLite backend used by the CLI and the Streamlit dashboard."""

    def __init__(self, path: str | None = None):
        self.path = path or get_settings().sqlite_path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.lock = threading.Lock()
        self._tables: set[str] = set()

    def _t(self, coll: str) -> str:
        if not IDENT.match(coll):
            raise ValueError("invalid collection name")
        if coll not in self._tables:
            with self.lock:
                self.conn.execute(f"CREATE TABLE IF NOT EXISTS {coll} (id TEXT PRIMARY KEY, created_at TEXT, data TEXT NOT NULL)")
                self.conn.commit()
            self._tables.add(coll)
        return coll

    def _upsert(self, coll, doc):
        t = self._t(coll)
        with self.lock:
            self.conn.execute(f"INSERT OR REPLACE INTO {t} (id, created_at, data) VALUES (?, ?, ?)",
                              (doc["id"], doc.get("created_at", ""), json.dumps(doc, default=str)))
            self.conn.commit()

    def _insert_if_absent(self, coll, doc):
        t = self._t(coll)
        with self.lock:
            cur = self.conn.execute(f"INSERT OR IGNORE INTO {t} (id, created_at, data) VALUES (?, ?, ?)",
                                    (doc["id"], doc.get("created_at", ""), json.dumps(doc, default=str)))
            self.conn.commit()
            return cur.rowcount == 1

    def _get(self, coll, doc_id):
        t = self._t(coll)
        with self.lock:
            row = self.conn.execute(f"SELECT data FROM {t} WHERE id = ?", (doc_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def _where(self, filters):
        clauses, args = [], []
        for k, v in (filters or {}).items():
            if not IDENT.match(k):
                raise ValueError("invalid filter field")
            clauses.append(f"json_extract(data, '$.{k}') = ?")
            args.append(int(v) if isinstance(v, bool) else v)
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", args

    def _find(self, coll, filters=None, sort="created_at", desc=True, limit=100, fields=None):
        t = self._t(coll)
        if not IDENT.match(sort):
            raise ValueError("invalid sort field")
        where, args = self._where(filters)
        q = f"SELECT data FROM {t}{where} ORDER BY json_extract(data, '$.{sort}') {'DESC' if desc else 'ASC'} LIMIT ?"
        with self.lock:
            rows = self.conn.execute(q, (*args, limit)).fetchall()
        docs = [json.loads(r[0]) for r in rows]
        return [{k: d.get(k) for k in fields} for d in docs] if fields else docs

    def _update(self, coll, doc_id, fields):
        doc = self._get(coll, doc_id)
        if doc:
            doc.update(fields)
            self._upsert(coll, doc)

    def _delete(self, coll, filters):
        t = self._t(coll)
        where, args = self._where(filters)
        with self.lock:
            cur = self.conn.execute(f"DELETE FROM {t}{where}", args)
            self.conn.commit()
            return cur.rowcount
