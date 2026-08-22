import pytest
from froide_payment.models import Plan

# AT's real plan name: DONATION_SITE_NAME_OVERRIDE is the legal recipient,
# "Forum Informationsfreiheit", which pushes the generated slug past the column.
AT_PLAN_NAME = "5 EUR Spende monatlich an Forum Informationsfreiheit"


@pytest.mark.django_db
def test_long_plan_slug_is_truncated_to_fit_the_column():
    """Regression: every recurring donation used to 500 here.

    froide-payment writes slug=slugify(plan_name) into a bare SlugField()
    (max_length 50). AT's name slugifies to 52 characters; DE's to 38, which is
    why upstream never hit it. See fds_donation.listeners.truncate_plan_slug.
    """
    from django.utils.text import slugify

    max_length = Plan._meta.get_field("slug").max_length
    assert len(slugify(AT_PLAN_NAME)) > max_length, (
        "This test is only meaningful while AT's plan name overflows the column. "
        "If froide-payment widened Plan.slug, drop the listener and this test."
    )

    plan = Plan.objects.create(
        name=AT_PLAN_NAME, slug=slugify(AT_PLAN_NAME), amount=5, interval=1
    )
    plan.refresh_from_db()

    assert len(plan.slug) <= max_length
    assert not plan.slug.endswith("-")
    # The name is a 256-char column and must survive intact -- it is what donors
    # and PayPal see.
    assert plan.name == AT_PLAN_NAME
