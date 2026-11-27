"""Settings for the local staging container (`.devcontainer/staging/`).

Production settings with every outbound channel cut: the staging database is a
copy of production, so it holds real users, donors and authorities, and
nothing in it may reach them. Mail goes to the console, faxes to the console
backend, payments to sandbox credentials (or nowhere), Sentry is off, and the
IMAP fetchers have no credentials.

Kept close to `FragDenStaat` otherwise (DEBUG off, cached templates, real
Celery workers, redis), because the point is to see production's behaviour.
"""

import os

from .base import env
from .production import FragDenStaat

# Production credentials in the environment would let a staging task act on
# live services: fetch and delete mail from the FOI or bounce mailbox, send a
# fax, charge a card, report to production's Sentry (production.py calls
# sentry_sdk.init() at import). The staging container sets none of them; refuse
# to start if one shows up anyway.
_FORBIDDEN_ENV_PREFIXES = (
    "DJANGO_SENTRY_",
    "DJANGO_FOI_EMAIL_",
    "DJANGO_BOUNCE_EMAIL_",
    "DJANGO_EMAIL_HOST",
    "TELNYX_",
    "STRIPE_PRIVATE_KEY",
    "STRIPE_WEBHOOK_",
    "PAYPAL_CLIENT_",
)
_forbidden = sorted(
    k for k in os.environ if k.startswith(_FORBIDDEN_ENV_PREFIXES) and os.environ[k]
)
if _forbidden:
    raise RuntimeError(
        "Production credentials must not be set for the staging settings: "
        + ", ".join(_forbidden)
    )


class Staging(FragDenStaat):
    SITE_URL = env("STAGING_SITE_URL", "http://localhost:8002")
    META_SITE_PROTOCOL = "http"
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
    CSRF_TRUSTED_ORIGINS = ["http://localhost:8002", "http://127.0.0.1:8002"]
    ALLOWED_REDIRECT_HOSTS = ALLOWED_HOSTS
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    LANGUAGE_COOKIE_SECURE = False
    SECURE_PROXY_SSL_HEADER = None

    SECRET_KEY = env("DJANGO_SECRET_KEY", "staging-only-not-secret")
    SECRET_URLS = {"admin": "admin"}

    # Outbound channels: none of these may reach a real person.
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    CELERY_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    FAX_BACKEND = "froide_fax.backends.console.ConsoleFaxBackend"
    TELNYX_APP_ID = None
    TELNYX_API_KEY = None
    TELNYX_PUBLIC_KEY = None
    TELNYX_FROM_NUMBER = None
    SENTRY_JS_URL = None

    PAYMENT_HOST = "localhost:8002"
    PAYMENT_USES_SSL = False
    # Production's variants with sandbox credentials (the STRIPE_TEST_* /
    # PAYPAL_TEST_* variables settings/test.py and Dev use). Unset, a payment
    # attempt fails at the provider instead of charging anyone.
    PAYMENT_VARIANTS = {
        **FragDenStaat.PAYMENT_VARIANTS,
        "creditcard": (
            "froide_payment.provider.StripeIntentProvider",
            {
                "public_key": env("STRIPE_TEST_PUBLIC_KEY"),
                "secret_key": env("STRIPE_TEST_SECRET_KEY"),
            },
        ),
        "sepa": (
            "froide_payment.provider.StripeSEPAProvider",
            {
                "public_key": env("STRIPE_TEST_PUBLIC_KEY"),
                "secret_key": env("STRIPE_TEST_SECRET_KEY"),
            },
        ),
        "paypal": (
            "froide_payment.provider.PaypalProvider",
            {
                "client_id": env("PAYPAL_TEST_CLIENT_ID"),
                "secret": env("PAYPAL_TEST_SECRET"),
                "endpoint": "https://api.sandbox.paypal.com",
                "capture": True,
                "webhook_id": None,
            },
        ),
    }

    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": env("DATABASE_NAME", "fragdenstaat_at"),
            "OPTIONS": {},
            "HOST": env("DATABASE_HOST", "db"),
            "USER": env("DATABASE_USER", "fragdenstaat_at"),
            "PASSWORD": env("DATABASE_PASSWORD", "fragdenstaat_at"),
            "CONN_MAX_AGE": 0,
            "PORT": "5432",
        }
    }
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    REDIS_URL = env("STAGING_REDIS_URL", "redis://redis:6379")
    CELERY_BROKER_URL = env("DJANGO_CELERY_BROKER_URL", "redis://redis:6379/0")
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [("redis", 6379)]},
        },
    }

    GEOIP_PATH = None
    MEDIA_ROOT = env("DJANGO_MEDIA_ROOT", "/srv/media")
    MEDIA_URL = "/files/"
    STATIC_URL = "/static/"
    STATIC_ROOT = env("DJANGO_STATIC_ROOT", "/srv/static")

    # runserver --insecure serves static files through the finders, which do
    # not know the hashed names ManifestStaticFilesStorage hands out. The
    # deploy-test script runs collectstatic once with STAGING_MANIFEST=1, to
    # catch what breaks production's collectstatic; browsing uses plain names.
    @property
    def STORAGES(self):
        storages = dict(FragDenStaat.STORAGES)
        if os.environ.get("STAGING_MANIFEST") != "1":
            storages["staticfiles"] = {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
            }
        return storages
