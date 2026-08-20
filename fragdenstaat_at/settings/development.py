from .base import FragDenStaatBase, env


class Dev(FragDenStaatBase):
    GEOIP_PATH = None
    FRONTEND_DEBUG = True

    DEBUG = True

    @property
    def INSTALLED_APPS(self):
        # Matches DE. Note the ordering difference from the daphne setup below:
        # DE appends, it does not prepend.
        return list(super().INSTALLED_APPS) + ["django_extended_makemessages"]

    # Deliberately NOT enabled -- was added in 2e53bad "as a hotfix for local
    # websocket issues", which made runserver an ASGI (Daphne) server.
    #
    # Six of the sixteen middlewares are sync-only (XForwardedFor,
    # AcceptNewTerms, and the four CMS ones including theme.cms_utils
    # .LanguageUtilsMiddleware -- no django-cms middleware declares
    # async_capable, so Django treats them all as sync). Under ASGI every
    # request therefore bridges sync<->async, and if the client disconnects
    # mid-request the bridge deadlocks: the main thread enters
    # ThreadSensitiveContext.__aexit__ and joins the executor while a pool
    # thread is still blocked in run_until_future waiting on that same
    # executor. Daphne then serves nothing until it is restarted. Observed
    # after a browser suspend (ERR_NETWORK_IO_SUSPENDED) during the
    # /anfrage-stellen/ flow.
    #
    # DE runs the plain WSGI dev server and is unaffected. Re-enable only for
    # websocket work (routing.py wires CMSPluginEditConsumer for CMS plugin
    # editing); prefer running Daphne separately on another port instead.
    #
    # @property
    # def INSTALLED_APPS(self):
    #     return ["daphne"] + list(super().INSTALLED_APPS)

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
