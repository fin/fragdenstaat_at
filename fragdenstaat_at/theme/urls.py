# monkeypatch as mentioned here: https://github.com/divio/django-cms/issues/6448

from cms import views as cms_views
from django.urls import get_resolver
from django.core.urlresolvers import LocaleRegexURLResolver
def _patch_lang_pfx():
    for url_pattern in get_resolver(None).url_patterns:
        if isinstance(url_pattern, LocaleRegexURLResolver):
            return url_pattern.prefix_default_language
    return False
# Swap out the faulty method from cms.views
cms_views.is_language_prefix_patterns_used = _patch_lang_pfx


from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.i18n import i18n_patterns
from django.contrib.sitemaps import views as sitemaps_views

from froide.foirequest.views import dashboard
from froide.urls import (
    froide_urlpatterns,
    admin_urls,
    jurisdiction_urls,
    sitemaps
)

from cms.sitemaps import CMSSitemap
sitemaps['cmspages'] = CMSSitemap

PROTOCOL = settings.SITE_URL.split(':')[0]

for klass in sitemaps.values():
    klass.protocol = PROTOCOL


sitemap_urlpatterns = [
    url(r'^sitemap\.xml$', sitemaps_views.index,
        {'sitemaps': sitemaps, 'sitemap_url_name': 'sitemaps'}),
    url(r'^sitemap-(?P<section>.+)\.xml$', sitemaps_views.sitemap,
        {'sitemaps': sitemaps}, name='sitemaps')
]

# could use i18n_patterns patterns here
urlpatterns = [
    # url(r'^$', index, name='index'),
    url(r'^dashboard/$', dashboard, name='dashboard'),
    url(r'^taggit_autosuggest/', include('taggit_autosuggest.urls')),
]

urlpatterns += [
    url(r'^', include('filer.server.urls')),
]

urlpatterns += sitemap_urlpatterns

if settings.DEBUG:
    from django.contrib.sites.models import Site  # noqa
    try:
        if not Site.objects.filter(id=settings.SITE_ID).exists():
            Site.objects.create(id=settings.SITE_ID,
                domain='localhost:8000', name='localhost')
    except Exception as e:
        # Possibly during migration, ignore
        pass


urlpatterns += i18n_patterns(
    *froide_urlpatterns,
    *jurisdiction_urls,
    *admin_urls,
    prefix_default_language=False
)

urlpatterns += [
    url(r'^', include('cms.urls')),
]
