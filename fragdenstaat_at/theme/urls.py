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

urlpatterns += (
    sitemap_urlpatterns +
    froide_urlpatterns +
    jurisdiction_urls
)


if settings.DEBUG:
    from django.contrib.sites.models import Site  # noqa
    try:
        if not Site.objects.filter(id=settings.SITE_ID).exists():
            Site.objects.create(id=settings.SITE_ID,
                domain='localhost:8000', name='localhost')
    except Exception as e:
        # Possibly during migration, ignore
        pass

urlpatterns += admin_urls + [
    url(r'^', include('cms.urls'))
]
