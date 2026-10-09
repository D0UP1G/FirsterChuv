"""ASGI entrypoint used by the API container."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")

application = get_asgi_application()
