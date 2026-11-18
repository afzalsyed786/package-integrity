import os

from pymongo import ASCENDING, DESCENDING, MongoClient

from .base import Store

INDEXED = {"analyses": ["created_at", "package", "ecosystem", "verdict"], "releases": ["ecosystem", "name", "published_at"],
           "alerts": ["created_at", "read"], "file_details": ["analysis_id"], "watchlist": ["created_at"]}


class MongoStore(Store):
    """MongoDB backend used by the hosted API (MONGO_URL / DB_NAME from the environment)."""

    def __init__(self, url: str | None = None, db_name: str | None = None):
        self.client = MongoClient(url or os.environ["MONGO_URL"])
        self.db = self.client[db_name or os.environ["DB_NAME"]]
        prefix = os.environ.get("PIA_COLLECTION_PREFIX", "pia_")
        self.prefix = prefix
        for coll, fields in INDEXED.items():
            c = self.db[prefix + coll]
            c.create_index([("id", ASCENDING)], unique=True)
            for f in fields:
                c.create_index([(f, DESCENDING)])

    def c(self, coll):
        return self.db[self.prefix + coll]

    def _upsert(self, coll, doc):
        self.c(coll).replace_one({"id": doc["id"]}, doc, upsert=True)
        doc.pop("_id", None)

    def _insert_if_absent(self, coll, doc):
        res = self.c(coll).update_one({"id": doc["id"]}, {"$setOnInsert": doc}, upsert=True)
        doc.pop("_id", None)
        return res.upserted_id is not None

    def _get(self, coll, doc_id):
        return self.c(coll).find_one({"id": doc_id}, {"_id": 0})

    def _find(self, coll, filters=None, sort="created_at", desc=True, limit=100, fields=None):
        proj = {"_id": 0, **({f: 1 for f in fields} if fields else {})}
        cur = self.c(coll).find(filters or {}, proj).sort(sort, DESCENDING if desc else ASCENDING).limit(limit)
        return list(cur)

    def _update(self, coll, doc_id, fields):
        self.c(coll).update_one({"id": doc_id}, {"$set": fields})

    def _delete(self, coll, filters):
        return self.c(coll).delete_many(filters).deleted_count
