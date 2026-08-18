import os

from configurations import values

from .base import THEME_ROOT, FragDenStaatBase, env, es_hosts


class Test(FragDenStaatBase):
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    ALLOWED_HOSTS = ("localhost", "testserver")

    DEBUG = False

    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]

    MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }

    TEST_SELENIUM_DRIVER = values.Value("chrome")
    ROOT_URLCONF = "tests.urls"

    GEOIP_PATH = None

    DATABASES = values.DatabaseURLValue(
        "postgis://fragdenstaat_at:fragdenstaat_at@localhost:5436/fragdenstaat_at"
    )
    ELASTICSEARCH_INDEX_PREFIX = "fds_test"
    ELASTICSEARCH_DSL = {
        "default": {
            "hosts": es_hosts(env("DJANGO_ELASTICSEARCH_HOSTS", "localhost:9200"))
        },
    }
    FIXTURE_DIRS = [os.path.join(THEME_ROOT, "..", "tests", "fixtures")]
