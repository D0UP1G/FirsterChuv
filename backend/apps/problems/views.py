from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.generics import ListAPIView
from rest_framework.pagination import LimitOffsetPagination

from backend.apps.accounts.permissions import IsApplicationAdmin

from .models import ProblemVersion
from .serializers import AdminProblemVersionSerializer


class ProblemVersionPagination(LimitOffsetPagination):
    default_limit = 25
    max_limit = 100


@method_decorator(csrf_protect, name="dispatch")
class AdminProblemVersionListView(ListAPIView):
    serializer_class = AdminProblemVersionSerializer
    permission_classes = [IsApplicationAdmin]
    pagination_class = ProblemVersionPagination
    queryset = (
        ProblemVersion.objects.select_related("public_data")
        .order_by("problem_id", "version")
    )

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
