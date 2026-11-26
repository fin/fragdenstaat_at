"""The donation embed fails closed (P7.2 group 2, AT's change to DE fb80c3bb)."""

from django.urls import reverse

import pytest
from cms.models import Page

from fragdenstaat_at.fds_cms.models import FdsPageExtension


@pytest.mark.django_db
def test_embed_is_only_framable_by_self_by_default(client):
    response = client.get(reverse("fds_donation:donate-embed"))
    assert response.status_code == 200
    assert "X-Frame-Options" not in response
    assert response["Content-Security-Policy"] == "frame-ancestors 'self'"


@pytest.mark.django_db
def test_embed_allows_partners_listed_on_the_donation_page(client):
    page = Page.objects.get(reverse_id="fds_donation")
    FdsPageExtension.objects.update_or_create(
        extended_object=page,
        defaults={"frame_ancestors": "https://partner.example.org"},
    )
    response = client.get(reverse("fds_donation:donate-embed"))
    assert response.status_code == 200
    assert response["Content-Security-Policy"] == (
        "frame-ancestors 'self' https://partner.example.org"
    )


@pytest.mark.django_db
def test_regular_donation_page_still_denies_framing(client):
    response = client.get(reverse("fds_donation:donate"))
    assert response.status_code == 200
    assert response["Content-Security-Policy"] == "frame-ancestors 'self'"
