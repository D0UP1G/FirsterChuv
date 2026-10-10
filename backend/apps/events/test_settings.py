"""Project settings that keep SQLite snapshot race tests file-backed."""

from copy import deepcopy
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from backend.config.settings import *  # noqa: F403


DATABASES = deepcopy(DATABASES)  # noqa: F405
DATABASES["default"]["TEST"] = {
    "NAME": str(Path(gettempdir()) / f"firsterchuv-events-{uuid4().hex}.sqlite3")
}
