from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": env("CACHE_DIR", default="/tmp/signage-cache"),
        "OPTIONS": {"MAX_ENTRIES": 2000},
    }
}

# The admin signs organizers in with a password and holds the upstream credentials, so it
# is only reachable over HTTPS: a plain request is redirected, and the cookies are never
# sent without TLS. The screens need no login. They may poll the API over plain HTTP on the
# venue network, which is why the API and the health check are exempt from the redirect.
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]"})
INSECURE_LOCAL = env.bool("DJANGO_INSECURE_LOCAL", default=False)
if INSECURE_LOCAL and not set(ALLOWED_HOSTS) <= LOOPBACK_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_INSECURE_LOCAL serves the admin without TLS, which is only for trying the "
        "stack on this machine: DJANGO_ALLOWED_HOSTS may then only list localhost addresses."
    )

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not INSECURE_LOCAL
SECURE_REDIRECT_EXEMPT = [r"^api/v1/", r"^health/"]
SESSION_COOKIE_SECURE = not INSECURE_LOCAL
CSRF_COOKIE_SECURE = not INSECURE_LOCAL
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=0)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "SAMEORIGIN"
