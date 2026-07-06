from django.contrib.auth import get_user_model
from django.test import TestCase

from cms.api import create_page
from djangocms_versioning.models import Version


class TestWebAppsForm(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_superuser(
            "admin", "admin@example.org", "password"
        )
        page = create_page("Home", "cms/home.html", "de-at", created_by=user)
        page_content = page.pagecontent_set(manager="admin_manager").first()
        Version.objects.get_for_content(page_content).publish(user)

    def test_homepage(self):
        response = self.client.get("/", follow=True)
        self.assertEqual(response.status_code, 200)

    def test_cms_search(self):
        response = self.client.get("/cms/search/")
        self.assertEqual(response.status_code, 200)
