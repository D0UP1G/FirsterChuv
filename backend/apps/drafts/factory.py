"""Resolve the real A2 workspace access port; never install a test fallback."""

from django.conf import settings
from django.utils.module_loading import import_string

from .errors import WorkspaceUnavailable
from .ports import WorkspaceAccess


def get_workspace_access() -> WorkspaceAccess:
    factory_path = getattr(settings, "WORKSPACE_ACCESS_FACTORY", None)
    if not factory_path:
        raise WorkspaceUnavailable("workspace access is unavailable")
    try:
        factory = import_string(factory_path)
        access = factory()
    except Exception as error:
        raise WorkspaceUnavailable("workspace access is unavailable") from error
    if not callable(getattr(access, "authorize_workspace", None)):
        raise WorkspaceUnavailable("workspace access is unavailable")
    return access
