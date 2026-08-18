from django.conf import settings
from django.urls import NoReverseMatch

from cms.app_base import CMSApp
from cms.apphook_pool import apphook_pool
from cms.models import Page

from froide.helper.search import search_registry

from .templatetags.fds_cms_tags import get_soft_root

# Only DE's search apphook is ported. Its other four (contact, plain API,
# datashow, scanner app) point at modules AT does not have.


def make_add_search(page_pk):
    def add_search(request):
        page = Page.objects.get(pk=page_pk)
        page_root = get_soft_root(page)
        if not page_root.has_translation(request.LANGUAGE_CODE):
            return
        try:
            return {
                "title": page_root.get_title(request.LANGUAGE_CODE),
                "menu_title": page_root.get_menu_title(request.LANGUAGE_CODE),
                "name": "cms-search-{}".format(page_root.pk),
                "url": page.get_absolute_url(request.LANGUAGE_CODE),
                "order": 7,
            }
        except NoReverseMatch:
            return

    return add_search


@apphook_pool.register
class FdsCmsSearchApp(CMSApp):
    name = "FragDenStaat-CMS-Suche"
    app_name = "fds_cms"

    def get_urls(self, page=None, language=None, **kwargs):
        # There is no ready() hook for apphooks, so registration piggybacks on
        # get_urls being called for each page the hook is attached to.
        if page is not None and language == settings.LANGUAGE_CODE:
            name = f"cms-search-{page.pk}"
            search_registry.register(make_add_search(page.pk), name)
        return ["fragdenstaat_at.fds_cms.urls"]
