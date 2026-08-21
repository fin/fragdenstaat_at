import pytest
from pytest_factoryboy import register

from froide.account.factories import UserFactory

from .. import models as donation_models
from .factories import DonorFactory

register(DonorFactory)


@pytest.fixture
def unsuspicious(monkeypatch):
    monkeypatch.setattr(
        donation_models, "check_suspicious_request", lambda *args, **kwargs: None
    )


@pytest.fixture
def dummy_user():
    yield UserFactory(username="dummy")


@pytest.fixture
def browser_context_args(browser_context_args):
    """Render third-party checkout pages in English.

    PayPal picks its language from the buyer's browser -- the one-off order path
    in froide-payment sets brand_name but no locale, so nothing on our side
    chooses it. With an Austrian sandbox buyer it lands on de_DE, and the
    English selectors in login_paypal ("Log In", "Next", "Continue") silently
    never match; the flow only works because the id-based selectors above them
    do.

    Safe for our own assertions: AT's LANGUAGES contains only de-at, so
    LocaleMiddleware serves German whatever Accept-Language says. Verified --
    /spenden/ returns Content-Language: de-at under en-US. Only third-party
    pages change.
    """
    return {**browser_context_args, "locale": "en-US"}
