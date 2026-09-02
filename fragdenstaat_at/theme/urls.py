from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib.sitemaps import views as sitemaps_views
from django.urls import include, path

from froide.urls import (
    admin_urls,
    api_urlpatterns,
    froide_urlpatterns,
    jurisdiction_urls,
    sitemaps,
)

from fragdenstaat_at.fds_cms.sitemaps import FdsCMSSitemap

from .views import (  # , glyphosat_download, meisterschaften_tippspiel
    FDSAnnotationView,
    extend_deadline_four_weeks,
    fax_letter_debug,
)

# Import early to register with api_router


sitemaps["cmspages"] = FdsCMSSitemap

PROTOCOL = settings.SITE_URL.split(":")[0]

for klass in sitemaps.values():
    klass.protocol = PROTOCOL


sitemap_urlpatterns = [
    path(
        "sitemap.xml",
        sitemaps_views.index,
        {"sitemaps": sitemaps, "sitemap_url_name": "sitemaps"},
    ),
    #     sitemaps_views.sitemap,
    #     {
    #     },
    # ),
    path(
        "sitemap-<slug:section>.xml",
        sitemaps_views.sitemap,
        {"sitemaps": sitemaps},
        name="sitemaps",
    ),
]

urlpatterns = [
    path("fax/", include("froide_fax.urls")),
    path("payments/", include("froide_payment.payments_urls")),
    path("payment/", include("froide_payment.urls")),
    path("fcdocs_annotate/", FDSAnnotationView.as_view(), name="annotate-view"),
    path(
        "r/<slug:slug>/frist-um-4-wochen-verlaengern/",
        extend_deadline_four_weeks,
        name="fds-extend-deadline-4weeks",
    ),
    # ),
    # ),
    # ),
    # ),
    # ),
    path(
        "spenden/",
        include("fragdenstaat_at.fds_donation.urls", namespace="fds_donation"),
    ),
]

urlpatterns += [
    path("", include("filer.server.urls")),
]

urlpatterns += api_urlpatterns
urlpatterns += sitemap_urlpatterns


if settings.DEBUG:
    # TEMPORARY: see fragdenstaat_at.theme.views.fax_letter_debug and
    # docs/qr-code-on-faxes.md. Delete once the fax QR layout is settled.
    urlpatterns += [
        path(
            "fax-letter-debug/request/<int:request_id>/",
            fax_letter_debug,
            name="fax-letter-debug-request",
        ),
        path(
            "fax-letter-debug/<int:message_id>/",
            fax_letter_debug,
            name="fax-letter-debug",
        ),
    ]

    from django.contrib.sites.models import Site  # noqa

    try:
        if not Site.objects.filter(id=settings.SITE_ID).exists():
            Site.objects.create(
                id=settings.SITE_ID, domain="localhost:8000", name="localhost"
            )
    except Exception:
        # Possibly during migration, ignore
        pass


urlpatterns += i18n_patterns(
    *froide_urlpatterns,
    *jurisdiction_urls,
    *admin_urls,
    path("cookies/", include("cookie_consent.urls")),
    path("", include("cms.urls")),
    prefix_default_language=False,
)
