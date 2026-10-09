"""Resolve the production submission service without installing test adapters."""

from django.conf import settings
from django.utils.module_loading import import_string

from .services import SubmissionService


def get_submission_service() -> SubmissionService:
    factory_path = getattr(settings, "SUBMISSION_SERVICE_FACTORY", None)
    if not factory_path:
        return SubmissionService(
            competition=None,
            event_writer=None,
            language_registry=None,
        )
    factory = import_string(factory_path)
    service = factory()
    if not isinstance(service, SubmissionService):
        raise TypeError("SUBMISSION_SERVICE_FACTORY must return SubmissionService")
    return service
