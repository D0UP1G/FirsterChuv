"""File-backed SQLite settings for persisted competition concurrency tests."""

from copy import deepcopy
import os
from pathlib import Path

from backend.config.settings import *  # noqa: F403

DATABASES = deepcopy(DATABASES)  # noqa: F405

test_database_path = Path(
    os.getenv(
        "COMPETITION_SQLITE_TEST_PATH",
        str(PROJECT_ROOT / ".data" / "competition-test.sqlite3"),  # noqa: F405
    )
)
test_database_path.parent.mkdir(parents=True, exist_ok=True)
DATABASES["default"]["TEST"] = {"NAME": str(test_database_path)}
DATABASES["default"]["OPTIONS"] = {
    **DATABASES["default"].get("OPTIONS", {}),
    "timeout": 0.25,
}
