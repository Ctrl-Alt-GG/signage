"""Settings shared by every environment. Values come from the environment or `.env`."""

from pathlib import Path

import environ

from config.storage import object_storage

BASE_DIR = Path(__file__).resolve().parents[3]

env = environ.FileAwareEnv()
if (env_file := BASE_DIR / ".env").exists():
    environ.Env.read_env(env_file)

DEBUG = env.bool("DJANGO_DEBUG", default=False)
SECRET_KEY = env("DJANGO_SECRET_KEY", default="development-key-not-for-production")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", default="http://localhost:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "solo",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "health_check",
    "signage.apps.SignageConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "src" / "signage" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'data' / 'db.sqlite3'}")
}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "signage",
    }
}
SOLO_CACHE = None

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "hu"
LANGUAGES = [("hu", "Magyar"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "src" / "locale"]
TIME_ZONE = env("TIME_ZONE", default="Europe/Budapest")
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Files. With STORAGE_ENDPOINT_URL set, static files and uploads live in an S3 bucket
# (MinIO in the Compose stack) and browsers load them from STORAGE_PUBLIC_URL; without it
# the local filesystem under data/ is used and runserver serves them (development).
STORAGE = object_storage(
    endpoint_url=env("STORAGE_ENDPOINT_URL", default=""),
    public_url=env("STORAGE_PUBLIC_URL", default=""),
    bucket=env("STORAGE_BUCKET", default="signage"),
    access_key=env("STORAGE_ACCESS_KEY", default=""),
    secret_key=env("STORAGE_SECRET_KEY", default=""),
    region=env("STORAGE_REGION", default="us-east-1"),
)
STORAGES = STORAGE.storages
STATIC_URL = STORAGE.static_url
MEDIA_URL = STORAGE.media_url
STATIC_ROOT = BASE_DIR / "data" / "staticfiles"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "data" / "media")))

# Where the display frontend is reachable from a browser, for the links in the admin.
# Empty means the same origin as the admin (the nginx frontend proxies /admin/).
DISPLAY_BASE_URL = env("DISPLAY_BASE_URL", default="").rstrip("/")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Ctrl-Alt-GG Signage API",
    "DESCRIPTION": (
        "Read-only JSON the display frontend polls. Content is managed in the Django admin."
    ),
    "VERSION": "1.0.0",
    "OAS_VERSION": "3.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "COMPONENT_SPLIT_REQUEST": True,
}

SIGNAGE_DEFAULT_SCREEN = env("SIGNAGE_DEFAULT_SCREEN", default="main")
SIGNAGE_CONTENT_DIR = BASE_DIR / "content"
SIGNAGE_LAST_GOOD_SECONDS = env.int("SIGNAGE_LAST_GOOD_SECONDS", default=3600)
SIGNAGE_THUMBNAIL_CACHE_SECONDS = env.int("SIGNAGE_THUMBNAIL_CACHE_SECONDS", default=20)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
