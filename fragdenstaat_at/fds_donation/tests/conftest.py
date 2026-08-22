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
    """Pin the browser to Austrian German, as a real donor would have it.

    Third-party checkout pages should render the way donors will actually see
    them. Concretely, the Stripe tests fill Stripe's own embedded card iframe by
    German placeholder (``get_by_placeholder("Kartennummer")``), and Stripe
    Elements follows the browser locale -- an English context renders "Card
    number" and those tests fail.

    An earlier version pinned en-US to make login_paypal's English selectors
    match. That was doubly wrong: it would have broken the Stripe card tests,
    and it does not even work on PayPal, which picks its language from
    country.x (de_DE/de_AT in the checkout URL) rather than Accept-Language.
    The PayPal selectors are keyed on ids and German text instead.

    Explicit rather than relying on the machine default, and harmless for our
    own pages: AT's LANGUAGES contains only de-at, so they are German whatever
    Accept-Language says.
    """
    return {**browser_context_args, "locale": "de-AT"}


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """Keep Chromium off /dev/shm.

    Docker gives a container 64 MB of shared memory by default, and Chromium
    puts renderer surfaces there. Exceed it and the tab dies with the unhelpful
    "Page crashed" -- which is how test_paypal_recurring failed on a plain
    page.goto() long after the payment itself had succeeded.

    --disable-dev-shm-usage makes Chromium use /tmp instead. Playwright does not
    pass it by default. The alternative is shm_size on the compose service,
    which needs a rebuild and does not travel with the repo.
    """
    args = list(browser_type_launch_args.get("args", []))
    if "--disable-dev-shm-usage" not in args:
        args.append("--disable-dev-shm-usage")
    return {**browser_type_launch_args, "args": args}
