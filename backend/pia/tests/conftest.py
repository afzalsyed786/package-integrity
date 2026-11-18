import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pia.config import get_settings  # noqa: E402
from pia.database.sqlite_store import SQLiteStore  # noqa: E402
from pia.engine.analyzer import Analyzer  # noqa: E402


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def store(tmp_path):
    return SQLiteStore(str(tmp_path / "test.sqlite3"))


@pytest.fixture
def analyzer(settings, store):
    return Analyzer(settings, store=store)
