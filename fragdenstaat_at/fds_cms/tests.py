"""CMS search pages in froide's search registry (DE 1de1d826, P7.2 group 5).

DE asserts on the search <select> its header renders on the login page. AT's
header does not render that dropdown, so these query the registry the header
would read instead -- the behaviour under test is make_add_search skipping
pages that were deleted or lost the apphook after registering.
"""

from django.test import RequestFactory

import pytest
from cms.models import Page

from froide.helper.search import search_registry

from tests.utils import reload_urls

LANGUAGE = "de-at"


@pytest.fixture
def search_page(cms_page):
    return cms_page(
        "Suche",
        LANGUAGE,
        slug="suche",
        apphook="FdsCmsSearchApp",
        apphook_namespace="fds_cms",
    )


def search_urls():
    request = RequestFactory().get("/")
    request.LANGUAGE_CODE = LANGUAGE
    return [item["url"] for item in search_registry.get_searches(request)]


@pytest.mark.django_db
class TestCmsSearchRegistry:
    def test_search_page_listed(self, search_page):
        assert search_page.get_absolute_url(LANGUAGE) in search_urls()

    def test_deleted_search_page_not_listed(self, search_page):
        url = search_page.get_absolute_url(LANGUAGE)
        Page.objects.get(pk=search_page.pk).delete()
        reload_urls()

        assert url not in search_urls()

    def test_page_without_search_apphook_not_listed(self, search_page):
        url = search_page.get_absolute_url(LANGUAGE)
        search_page.application_urls = ""
        search_page.application_namespace = None
        search_page.save()
        reload_urls()

        assert url not in search_urls()
