import os

from configurations import values

# The async browser tests (fds_donation/tests/test_banktransfer.py, test_stripe.py)
# touch the ORM from an async context. DE sets this in its settings/test.py; AT
# previously set it in tests/conftest.py, which only covers tests/ -- so the
# fds_donation tests failed with SynchronousOnlyOperation.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

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
    # Adopted from DE's test settings alongside its fds_donation tests, which
    # exercise every variant. The Stripe/PayPal ones need test keys from the
    # environment; the tests that use them are marked and deselected by default
    # (see pytest.ini), but the variants must still be declared or unrelated
    # tests fail with "Payment variant does not exist".
    PAYMENT_VARIANTS = {
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
        "lastschrift": ("froide_payment.provider.LastschriftProvider", {}),
        "banktransfer": ("froide_payment.provider.BanktransferProvider", {}),
    }

    ELASTICSEARCH_INDEX_PREFIX = "fds_test"
    ELASTICSEARCH_DSL = {
        "default": {
            "hosts": es_hosts(env("DJANGO_ELASTICSEARCH_HOSTS", "localhost:9200"))
        },
    }
    FIXTURE_DIRS = [os.path.join(THEME_ROOT, "..", "tests", "fixtures")]
