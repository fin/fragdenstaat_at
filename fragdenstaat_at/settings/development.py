from .base import FragDenStaatBase, env


class Dev(FragDenStaatBase):
    GEOIP_PATH = None
    FRONTEND_DEBUG = True

    @property
    def INSTALLED_APPS(self):
        return ["daphne"] + list(super().INSTALLED_APPS)

    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    CELERY_EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    FRONTEND_SERVER_URL = "http://localhost:5173/static/"

    CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": env("DATABASE_NAME", "fragdenstaat_at"),
            "OPTIONS": {},
            "HOST": env("DATABASE_HOST", "localhost"),
            "USER": env("DATABASE_USER", "fragdenstaat_at"),
            "PASSWORD": env("DATABASE_PASSWORD", "fragdenstaat_at"),
            "PORT": "5432",
        }
    }

    @property
    def TEMPLATES(self):
        TEMP = super().TEMPLATES
        TEMP[0]["OPTIONS"]["debug"] = True
        return TEMP



try:
    from .local_settings import Dev  # noqa
except ImportError:
    pass
