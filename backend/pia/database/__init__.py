from .base import Store
from .sqlite_store import SQLiteStore


def get_store(backend: str | None = None, **kw) -> Store:
    if backend == "mongo":
        from .mongo_store import MongoStore

        return MongoStore(**kw)
    return SQLiteStore(**kw)


__all__ = ["Store", "SQLiteStore", "get_store"]
