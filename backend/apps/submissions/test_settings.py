"""File-backed SQLite settings for queue admission concurrency tests."""

from copy import deepcopy
import os
from pathlib import Path

from backend.config.settings import *  # noqa: F403

DATABASES = deepcopy(DATABASES)  # noqa: F405
test_database_path = Path(
    os.getenv("SQLITE_TEST_PATH", str(PROJECT_ROOT / ".data" / "submissions-test.sqlite3"))  # noqa: F405
)
test_database_path.parent.mkdir(parents=True, exist_ok=True)
DATABASES["default"]["TEST"] = {"NAME": str(test_database_path)}
