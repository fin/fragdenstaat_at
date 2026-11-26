from django.conf import settings


def page_site_settings(request, key, default=None):
    current_page = getattr(request, "current_page", None)
    if current_page and current_page.site_id != settings.SITE_ID:
        return current_page.site.site_settings.settings.get(key, default)
    return default


def theme_settings(request):
    return {
        "SENTRY_JS_URL": settings.SENTRY_JS_URL,
        # DE's template hierarchy reads this. AT is single-site, so
        # page_site_settings always returns the default.
        "MAINSITE_BASE_TEMPLATE": page_site_settings(
            request, "CMSSITE_BASE_TEMPLATE", "cms/base.html"
        ),
    }


def site_settings(request):
    site_settings = request.site.site_settings.settings
    return site_settings
