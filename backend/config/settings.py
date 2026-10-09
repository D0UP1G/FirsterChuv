"""Settings for the FirsterChuv API and trusted management processes."""

import os
import secrets
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean value")


def env_csv(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
REQUIRE_SECRET_KEY = env_bool("DJANGO_REQUIRE_SECRET_KEY", not DEBUG)
configured_secret_key = os.getenv("DJANGO_SECRET_KEY", "").strip()
if REQUIRE_SECRET_KEY and (not configured_secret_key or configured_secret_key == "replace-before-sharing"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a private value")
SECRET_KEY = configured_secret_key or secrets.token_urlsafe(50)

ALLOWED_HOSTS = env_csv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,api")
CSRF_TRUSTED_ORIGINS = env_csv("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8080")
CSRF_FAILURE_VIEW = "backend.apps.common.views.csrf_failure"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "backend.apps.common.apps.CommonConfig",
    "backend.apps.accounts.apps.AccountsConfig",
    "backend.apps.tournaments.apps.TournamentsConfig",
    "backend.apps.competition.apps.CompetitionConfig",
    "backend.apps.submissions.apps.SubmissionsConfig",
    "backend.apps.events.apps.EventsConfig",
    "backend.apps.problems.apps.ProblemsConfig",
    "backend.apps.judge.apps.JudgeConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "backend.apps.common.middleware.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "backend.config.urls"
ASGI_APPLICATION = "backend.config.asgi.application"
WSGI_APPLICATION = "backend.config.wsgi.application"
APPEND_SLASH = False

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = PROJECT_ROOT / ".data" / "static"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

sqlite_path = Path(os.getenv("SQLITE_PATH", ".data/db.sqlite3"))
if not sqlite_path.is_absolute():
    sqlite_path = PROJECT_ROOT / sqlite_path
sqlite_timeout = float(os.getenv("SQLITE_TIMEOUT", "5"))
if sqlite_timeout <= 0:
    raise ImproperlyConfigured("SQLITE_TIMEOUT must be positive")
sqlite_path.parent.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": sqlite_path,
        "OPTIONS": {"timeout": sqlite_timeout},
        "CONN_MAX_AGE": 0,
    }
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "backend.apps.common.api.CamelCaseJSONParser",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "backend.apps.common.api.CamelCaseJSONRenderer",
    ],
    "EXCEPTION_HANDLER": "backend.apps.common.api.exception_handler",
    # Compose has one trusted Nginx hop; adjust NUM_PROXIES with deployment topology.
    "NUM_PROXIES": 1,
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": "10/minute",
        "auth_register": "20/hour",
        "invite_preview": "30/minute",
        "submission": "30/minute",
    },
    "DATETIME_FORMAT": "iso-8601",
}
