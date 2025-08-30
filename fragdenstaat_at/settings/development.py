from .base import FragDenStaatBase, env


class Dev(FragDenStaatBase):
    GEOIP_PATH = None
    FRONTEND_DEBUG = False

    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    CELERY_EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

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
        print('devtemplates', TEMP)
        return TEMP



try:
    from .local_settings import Dev  # noqa
except ImportError:
    pass
