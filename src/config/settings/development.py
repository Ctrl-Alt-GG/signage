from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, BASE_DIR, env

DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = [*ALLOWED_HOSTS, "testserver"]
INTERNAL_IPS = ["127.0.0.1"]
(BASE_DIR / "data").mkdir(exist_ok=True)
