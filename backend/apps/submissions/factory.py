"""Resolve the production submission service without installing test adapters."""

from django.conf import settings
from django.utils.module_loading import import_string

from .errors import IntegrationUnavailable
from .services import SubmissionService
from .worker import SubmissionWorker


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


def get_submission_worker() -> SubmissionWorker:
    """Resolve a fully wired production worker; never install test adapters."""
    factory_path = getattr(settings, "SUBMISSION_WORKER_FACTORY", None)
    if not factory_path:
        raise IntegrationUnavailable(
            "submission worker is unavailable until SUBMISSION_WORKER_FACTORY is configured"
        )
    factory = import_string(factory_path)
    worker = factory()
    if not isinstance(worker, SubmissionWorker):
        raise TypeError("SUBMISSION_WORKER_FACTORY must return SubmissionWorker")
    return worker
