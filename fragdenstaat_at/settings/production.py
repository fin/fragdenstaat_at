import os

import django_cache_url

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from .base import FragDenStaatBase, env


class FragDenStaat(FragDenStaatBase):
    DEBUG = False
    TEMPLATE_DEBUG = False
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_EAGER_PROPAGATES = False
    CELERY_SEND_TASK_ERROR_EMAILS = True

    ADMINS = (('FragDenStaat.at', 'mail@fragdenstaat.at'),)
    MANAGERS = (('FragDenStaat.at', 'mail@fragdenstaat.at'),)

    SECURE_FRAME_DENY = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True

    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

    DATA_UPLOAD_MAX_MEMORY_SIZE = 15728640
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
    STATIC_URL = 'https://static.frag.denstaat.at/static/'

    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTOCOL', 'https')

    INTERNAL_MEDIA_PREFIX = '/protected/'

    ALLOWED_HOSTS = ('fragdenstaat.at', 'media.frag.denstaat.at', 'testserver')
    ALLOWED_REDIRECT_HOSTS = ('fragdenstaat.at',)

    CACHES = {'default': django_cache_url.config()}

    DATABASES = {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.postgis',
            'NAME': env('DATABASE_NAME'),
            'OPTIONS': {},
            'HOST': env('DATABASE_HOST'),
            'USER': env('DATABASE_USER'),
            'PASSWORD': env('DATABASE_PASSWORD'),
            'CONN_MAX_AGE': 0,
            'PORT': '',
        }
    }

    @property
    def TEMPLATES(self):
        TEMP = super(FragDenStaat, self).TEMPLATES
        TEMP[0]['OPTIONS']['debug'] = False
        loaders = TEMP[0]['OPTIONS']['loaders']
        TEMP[0]['OPTIONS']['loaders'] = [
            ('django.template.loaders.cached.Loader', loaders)
        ]
        return TEMP

    CELERY_BROKER_URL = env('DJANGO_CELERY_BROKER_URL')

    CUSTOM_AUTH_USER_MODEL_DB = 'auth_user'

    DEFAULT_FROM_EMAIL = 'FragDenStaat.at <info@fragdenstaat.at>'
    EMAIL_BACKEND = 'fragdenstaat_at.theme.email_backend.CustomCeleryEmailBackend'
    CELERY_EMAIL_BACKEND = 'froide.foirequest.smtp.EmailBackend'
    # EMAIL_HOST
    # EMAIL_HOST_PASSWORD
    # EMAIL_HOST_USER
    EMAIL_SUBJECT_PREFIX = '[AdminFragDenStaat] '
    EMAIL_USE_TLS = True
    EMAIL_PORT = 25
    # FOI_EMAIL_ACCOUNT_NAME
    # FOI_EMAIL_ACCOUNT_PASSWORD
    FOI_EMAIL_DOMAIN = ['foi.fragdenstaat.at']
    FOI_EMAIL_FIXED_FROM_ADDRESS = False
    FOI_EMAIL_FUNC = None
    # Values from env
    # FOI_EMAIL_HOST
    # FOI_EMAIL_HOST_FROM
    # FOI_EMAIL_HOST_IMAP
    # FOI_EMAIL_HOST_PASSWORD
    # FOI_EMAIL_HOST_USER
    FOI_EMAIL_PORT = 25
    FOI_EMAIL_PORT_IMAP = 143
    FOI_EMAIL_USE_SSL = False
    FOI_EMAIL_USE_TLS = True
    FOI_MEDIA_PATH = 'foi'

    BOUNCE_EMAIL_PORT_IMAP = 143

    GEOIP_PATH = env('DJANGO_GEOIP_PATH')

    ELASTICSEARCH_INDEX_PREFIX = 'fragdenstaat_at'
    ELASTICSEARCH_DSL = {
        'default': {
            'hosts': 'localhost:{}'.format(env('FROIDE_ELASTICSEARCH_PORT','9200'))
        },
    }
    ELASTICSEARCH_DSL_SIGNAL_PROCESSOR = 'froide.helper.search.CelerySignalProcessor'

    LOGGING = {
        'loggers': {
            'froide': {
                'level': 'INFO',
                'propagate': True,
                'handlers': ['normal']
            },
            'sentry.errors': {
                'handlers': ['normal'],
                'propagate': False,
                'level': 'DEBUG'
            },
            'django.request': {
                'level': 'ERROR',
                'propagate': True,
                'handlers': ['normal']
            },
        },
        'disable_existing_loggers': True,
        'handlers': {
            'normal': {
                'filename': os.path.join(env('DJANGO_LOG_DIR'), 'froide.log'),
                'class': 'logging.FileHandler',
                'level': 'INFO'
            }
        },
        'formatters': {
            'verbose': {
                'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
            }
        },
        'version': 1,
        'filters': {
            'require_debug_false': {
                '()': 'django.utils.log.RequireDebugFalse'
            }
        },
        'root': {
            'handlers': ['normal'],
            'level': 'WARNING'
        }
    }
    MANAGERS = (('FragDenStaat.at', 'mail@fragdenstaat.at'),)
    MEDIA_ROOT = env('DJANGO_MEDIA_ROOT')
    MEDIA_URL = 'https://media.frag.denstaat.at/files/'

    FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o2750
    FILE_UPLOAD_PERMISSIONS = 0o640

    SECRET_KEY = env('DJANGO_SECRET_KEY')
    SECRET_URLS = {
        'admin': env('DJANGO_SECRET_URL_ADMIN')
    }

    _base_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..')
    )

    SENTRY_JS_URL = env('DJANGO_SENTRY_PUBLIC_DSN')
    SERVER_EMAIL = 'info@fragdenstaat.at'

    SITE_EMAIL = 'info@fragdenstaat.at'
    SITE_ID = 1
    SITE_NAME = 'FragDenStaat.at'
    SITE_URL = 'https://fragdenstaat.at'
    META_SITE_PROTOCOL = 'https'

    TASTYPIE_DEFAULT_FORMATS = ['json']

    @property
    def OAUTH2_PROVIDER(self):
        P = super(FragDenStaat, self).OAUTH2_PROVIDER
        P['ALLOWED_REDIRECT_URI_SCHEMES'] = ['https', 'fragdenstaat']
        return P


sentry_sdk.init(
    dsn=env('DJANGO_SENTRY_DSN'),
    integrations=[DjangoIntegration()]
)
