from contextlib import closing
from datetime import datetime, timedelta
import re
import socket

from django.contrib.staticfiles.storage import StaticFilesStorage

from .base import FragDenStaatBase, env


CHECK_WEBPACK = {"timestamp": None, "result": False}
CHECK_WEBPACK_SECONDS = timedelta(seconds=5)



def use_webpack_dev_server():
    now = datetime.now()
    if (
        CHECK_WEBPACK["timestamp"] is None
        or now - CHECK_WEBPACK["timestamp"] > CHECK_WEBPACK_SECONDS
    ):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("127.0.0.1", 8080)) == 0
        CHECK_WEBPACK["timestamp"] = now
        if result != CHECK_WEBPACK["result"]:
            if result:
                print("Switching to webpack dev server")
            else:
                print("Switching to Django static file server")
        CHECK_WEBPACK["result"] = result
    return CHECK_WEBPACK["result"]


WEBPACK_PATTERN = re.compile(r"(css|js)/[\w-]+\.(css|js)$")


class WebpackDevStaticFilesStorage(StaticFilesStorage):
    def url(self, name):
        if WEBPACK_PATTERN.match(name):
            if use_webpack_dev_server():
                return "http://localhost:8080/static/" + name
        return super(WebpackDevStaticFilesStorage, self).url(name)



class Dev(FragDenStaatBase):
    GEOIP_PATH = None

    CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": env("DATABASE_NAME", "fragdenstaat_at"),
            "OPTIONS": {},
            "HOST": "localhost",
            "USER": env("DATABASE_USER", "fragdenstaat_at"),
            "PASSWORD": env("DATABASE_PASSWORD", "fragdenstaat_at"),
            "PORT": "5432",
        }
    }

    STATICFILES_STORAGE = (
        "fragdenstaat_at.settings.development.WebpackDevStaticFilesStorage"
    )


try:
    from .local_settings import Dev  # noqa
except ImportError:
    pass
