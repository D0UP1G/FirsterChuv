"""Session-based authentication endpoints for the global account roles."""

from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from backend.apps.accounts.serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserSummarySerializer,
)


def _no_store(response):
    response["Cache-Control"] = "no-store"
    return response


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return _no_store(Response({"csrf_token": get_token(request._request)}))


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return _no_store(
            Response(UserSummarySerializer(user).data, status=201)
        )


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credentials = serializer.validated_data
        user = authenticate(
            request=request._request,
            username=credentials["email"],
            password=credentials["password"],
        )
        if user is None:
            raise AuthenticationFailed("Неверный email или пароль.")

        django_login(request._request, user)
        user_data = UserSummarySerializer(user).data
        user_data["csrf_token"] = get_token(request._request)
        return _no_store(Response(user_data))


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        django_logout(request._request)
        return _no_store(Response(status=204))


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return _no_store(Response(UserSummarySerializer(request.user).data))
