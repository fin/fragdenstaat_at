import asyncio
import os
import pathlib
import re
import tempfile
import time
from decimal import Decimal

from django.urls import reverse

import payments.core
import pytest
from playwright.async_api import Page

from fragdenstaat_at.fds_donation.models import Donation

from .utils import ProcessReader


class PaypalWebhookForwarder:
    # WEBHOOK_URL_RE = re.compile(r"https://\w+.serveo.net")
    # HTTP_RE = re.compile(r"HTTP request from")
    WEBHOOK_URL_RE = re.compile(r"https://[-\w]+.loca.lt")
    HTTP_RE = re.compile(r"(?:GET|POST) /")

    def __init__(self, forward_url: str):
        forward_url = forward_url.replace("http://", "")
        host, path = forward_url.split("/", 1)
        self.forward_host = host
        self.forward_port = host.split(":")[-1]
        self.forward_path = "/" + path
        self.webhook_url = None
        self.paypal_webhook_id = None
        self.max_request_count = 2
        self.target_event_set = set()
        self.seen_event_set = set()
        self.webhook_data = []

    def setup_webhook(self):
        # process_args = [
        #     "ssh",
        #     "-o",
        #     "StrictHostKeyChecking=no",
        #     "-n",  # Redirect stdin from /dev/null
        #     "-T",  # Disable pseudo-tty allocation
        #     "-R",
        #     "80:{}".format(self.forward_host),
        #     # Some guys forwarding service because Paypal doesn't have a cli like stripe
        #     "serveo.net",
        # ]
        process_args = ["lt", "--port", self.forward_port, "--print-requests"]
        self.proc = ProcessReader(process_args)
        self.proc.start()
        line = self.proc.readline()
        match = self.WEBHOOK_URL_RE.search(line)
        if match:
            self.webhook_url = match.group(0)
        if self.webhook_url is None:
            raise Exception(f"Could not find webhook URL in output: {line!r}")
        return self.set_webhook_on_paypal(self.webhook_url)

    def _verify_webhook(self, request, data):
        self.webhook_data.append(data)
        self.seen_event_set.add(data["event_type"])
        return self._real_verify_webhook(request, data)

    def set_webhook_on_paypal(self, webhook_url):
        paypal_provider = payments.core.provider_factory("paypal")
        assert "sandbox" in paypal_provider.endpoint

        # Hook verify webhook to capture data
        self._real_verify_webhook = paypal_provider.verify_webhook
        paypal_provider.verify_webhook = self._verify_webhook

        response = paypal_provider.post_api(
            "{}/v1/notifications/webhooks".format(paypal_provider.endpoint),
            {
                "url": "{webhook_url}{path}".format(
                    webhook_url=webhook_url, path=self.forward_path
                ),
                "event_types": [
                    {"name": "*"},
                ],
            },
        )
        self.paypal_webhook_id = response["id"]
        self.old_webhook_id = paypal_provider.webhook_id
        paypal_provider.webhook_id = self.paypal_webhook_id
        return self.paypal_webhook_id

    def delete_webhook_on_paypal(self):
        paypal_provider = payments.core.provider_factory("paypal")
        assert "sandbox" in paypal_provider.endpoint
        paypal_provider.post_api(
            "{}/v1/notifications/webhooks/{}".format(
                paypal_provider.endpoint, self.paypal_webhook_id
            ),
            None,
            method="DELETE",
        )
        paypal_provider.webhook_id = self.old_webhook_id
        paypal_provider.verify_webhook = self._real_verify_webhook

    def __enter__(self):
        self.setup_webhook()

    def __exit__(self, exc_type, exc_val, exc_tb):
        http_request_count = 0
        try:
            if exc_val is None:
                while True:
                    line = self.proc.readline()
                    print("Forwarder Log", repr(line.encode("utf-8")))
                    if self.HTTP_RE.search(line):
                        http_request_count += 1
                    if http_request_count >= self.max_request_count:
                        break
                    time.sleep(0.1)
                    if self.target_event_set and not len(
                        self.target_event_set - self.seen_event_set
                    ):
                        break
        finally:
            self.delete_webhook_on_paypal()
            self.proc.stop()


@pytest.fixture
def paypal_setup(settings, live_server, monkeypatch):
    """
    Sets up settings to handle payments with paypal via live_server.
    The fixture itself is a context manager that captures webhooks.
    """
    settings.SITE_URL = live_server.url
    settings.ALLOWED_HOSTS = ["*"]
    # PAYMENT_HOST setting is copied to module level on import, need to patch it
    monkeypatch.setattr(
        payments.core, "PAYMENT_HOST", live_server.url.replace("http://", "")
    )

    webhook_url = live_server.url + "/payments/process/paypal/"
    forwarder = PaypalWebhookForwarder(webhook_url)
    yield forwarder


async def fill_donation_page(page: Page, donor_email):
    await page.get_by_placeholder("Vorname").fill("Peter")
    await page.get_by_placeholder("Nachname").fill("Parker")
    await page.get_by_placeholder("z.B. name@beispiel.de").fill(donor_email)
    # Opt out of the donation receipt and the user account. Addressed by field
    # id, not by get_by_text(...).nth(): DE's form has a third "Nein, danke."
    # (the contact/newsletter opt-in) ahead of these two, which D3 removes on AT,
    # so DE's indices 1 and 2 silently point at the wrong controls here.
    await page.locator("#id_receipt_0").click()
    await page.locator("#id_account_1").click()
    await page.get_by_label("Was ist drei plus vier?").fill("7")


async def try_selectors(
    page: Page,
    selectors: list[str],
    value: str | None = None,
    force: bool = False,
):
    """Fill or click the first matching selector. Returns whether it worked.

    ``force`` skips Playwright's actionability checks. PayPal's login page
    renders a #signupContainer whose .loginSignUpSeparator overlays the submit
    button, so an ordinary click spends 30s retrying "element intercepts pointer
    events" and then gives up -- the button is perfectly clickable, it just is
    not the topmost node at its centre point.
    """
    for sel in selectors:
        try:
            print("trying", sel)
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                print("found element", sel, value)
                if value:
                    await el.fill(value)
                else:
                    await el.click(force=force)
                return True
        except Exception as e:
            print(e)
            continue
    print("failed")
    return False


LOGIN_TIMEOUT = 60
LOGIN_URL_RE = re.compile(r"/(signin|webapps/xoonboarding|connect)", re.I)


async def left_login_page(page: Page, previous_url: str, timeout: int = 20) -> bool:
    """Wait until the URL changes away from the login step."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.url != previous_url and not LOGIN_URL_RE.search(page.url):
            return True
        await asyncio.sleep(0.5)
    return page.url != previous_url and not LOGIN_URL_RE.search(page.url)


async def fail_with_page_state(page: Page, what: str, hint: str):
    """Raise with the page URL, title, a screenshot and the raw HTML."""
    slug = what.replace(" ", "-")
    shot = pathlib.Path(tempfile.gettempdir()) / f"paypal-{slug}.png"
    html = shot.with_suffix(".html")
    try:
        await page.screenshot(path=str(shot), full_page=True)
        html.write_text(await page.content(), encoding="utf-8")
        saved = f"  screenshot: {shot}\n  html      : {html}\n"
    except Exception as exc:  # pragma: no cover - diagnostics only
        saved = f"  (could not capture page: {exc})\n"
    raise AssertionError(
        f"PayPal: {what}.\n"
        f"  page url  : {page.url}\n"
        f"  page title: {await page.title()!r}\n"
        f"{saved}{hint}"
    )


async def retry_selectors(page: Page, selectors, value, what: str, force=False):
    """Poll for one of *selectors*, giving up after LOGIN_TIMEOUT seconds.

    These used to be `while not entered: ...` with no bound, which meant the
    test could only ever hang -- never fail. If the flow does not reach PayPal
    (a locator change on our own donation form is enough), the loop polls a
    localhost page for a PayPal login field forever, at 1s intervals and near
    zero CPU, so it looks like a slow test rather than a broken one. Ctrl-C then
    lands in asyncio internals and names nothing useful.

    Failing here instead reports where the browser actually is, which is the
    fact you need.
    """
    deadline = time.monotonic() + LOGIN_TIMEOUT
    while time.monotonic() < deadline:
        if await try_selectors(page, selectors, value, force=force):
            return True
        await asyncio.sleep(1)

    # Playwright is driven over --remote-debugging-pipe, so the browser cannot
    # be inspected from outside the test process. Capture the evidence here or
    # it is lost when the run ends.
    shot = pathlib.Path(tempfile.gettempdir()) / f"paypal-login-{what.split()[0]}.png"
    html = shot.with_suffix(".html")
    try:
        await page.screenshot(path=str(shot), full_page=True)
        html.write_text(await page.content(), encoding="utf-8")
        saved = f"  screenshot: {shot}\n  html      : {html}\n"
    except Exception as exc:  # pragma: no cover - diagnostics only
        saved = f"  (could not capture page: {exc})\n"

    raise AssertionError(
        f"PayPal {what} did not appear within {LOGIN_TIMEOUT}s.\n"
        f"  tried     : {selectors}\n"
        f"  page url  : {page.url}\n"
        f"  page title: {await page.title()!r}\n"
        f"{saved}"
        "If the URL is not on paypal.com the donation form never redirected -- "
        "look there, not at the login helper."
    )


async def login_paypal(page: Page):
    test_account = os.environ["PAYPAL_TEST_ACCOUNT"]
    test_password = os.environ["PAYPAL_TEST_PASSWORD"]
    email_selectors = [
        "input#email",
        "input[type=email]",
        "input[name=email]",
        "input[name=login_email]",
    ]
    password_selectors = [
        "input#password",
        "input[type=password]",
        "input[name='login_password']",
    ]
    next_selectors = [
        "button:has-text('Next')",
        "button:has-text('Continue')",
    ]
    login_selectors = [
        "button#btnLogin",
        "button[name='action']",
        "button[value='submitPassword']",
        "button:has-text('Log In')",
        "button:has-text('Log in')",
    ]
    await retry_selectors(page, email_selectors, test_account, what="email field")

    print("clicking button")
    await try_selectors(page, next_selectors)
    await asyncio.sleep(1)
    await retry_selectors(
        page, password_selectors, test_password, what="password field"
    )
    # Submit by pressing Enter in the password field rather than clicking.
    # #btnLogin is overlaid by .loginSignUpSeparator, and force=True is not a
    # fix for that: it skips the actionability *check*, but the click still
    # lands on whatever occupies the centre point -- the overlay. That reported
    # success while never submitting, and the failure only surfaced pages later
    # as a confusing strict-mode violation on the pay button.
    login_url = page.url
    await page.keyboard.press("Enter")
    if not await left_login_page(page, login_url):
        # Fall back to the button, still forced, in case Enter is swallowed.
        await retry_selectors(
            page, login_selectors, None, what="login button", force=True
        )
        if not await left_login_page(page, login_url):
            await fail_with_page_state(
                page,
                "login did not submit",
                "Filled both fields but the page never left the login step. "
                "#btnLogin is overlaid by .loginSignUpSeparator, so a click can "
                "be swallowed by the overlay.",
            )


DONATION_DONE_URL = re.compile(r".*spenden/spende/spenden/abgeschlossen/.*")
DONATION_FAILED_URL = re.compile(r".*spenden/spende/spenden/fehlgeschlagen/.*")


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.django_db
@pytest.mark.paypal
async def test_paypal_once(page: Page, live_server, paypal_setup):
    donor_email = "peter.parker@example.com"

    await page.goto(live_server.url + reverse("fds_donation:donate"))
    await page.get_by_role("button", name="5 Euro").click()
    await page.get_by_text("Paypal", exact=True).click()
    await fill_donation_page(page, donor_email)

    await page.get_by_role("button", name="Jetzt spenden").click()

    await login_paypal(page)

    donation = Donation.objects.filter(
        donor__email=donor_email, amount=5, recurring=False, method="paypal"
    ).latest("timestamp")
    assert donation.received_timestamp is None
    assert donation.payment.status == "input"

    # Checkout order approved + payment capture completed
    paypal_setup.max_request_count = 2
    with paypal_setup:
        # Not locator("button", has_text="Pay"): "Pay" is a substring of
        # "PayPal", so on any page still showing PayPal branding it matches
        # several buttons and raises a strict-mode violation that says nothing
        # about the real problem. Target the actual submit control instead.
        pay_button = page.locator(
            "#payment-submit-btn, button[data-testid='submit-button-initial']"
        ).first
        await pay_button.wait_for(state="visible", timeout=30000)
        await pay_button.click()
        await page.wait_for_url(DONATION_DONE_URL)

        assert await page.get_by_text("Vielen Dank für Ihre Spende!").is_visible()
        assert await page.get_by_text(donor_email).is_visible()

        print("Waiting for webhooks...")

    donation.refresh_from_db()
    assert donation.completed is True
    assert donation.received_timestamp is not None
    payment = donation.payment
    assert payment.status == "confirmed"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.django_db
@pytest.mark.paypal
async def test_paypal_recurring(page: Page, live_server, paypal_setup):
    donor_email = "peter.parker@example.com"

    await page.goto(live_server.url + reverse("fds_donation:donate"))
    await page.get_by_role("button", name="5 Euro").click()
    await page.get_by_text("monatlich").click()
    await page.get_by_text("Paypal", exact=True).click()
    await fill_donation_page(page, donor_email)

    # Sometimes: Billing plan created + catalog product created, billing subscription created
    # Always: payment sale completed + billing subscription activated
    paypal_setup.max_request_count = 5
    paypal_setup.target_event_set = {
        "BILLING.SUBSCRIPTION.ACTIVATED",
        "PAYMENT.SALE.COMPLETED",
    }
    with paypal_setup:
        await page.get_by_role("button", name="Jetzt spenden").click()

        await login_paypal(page)

        donation = Donation.objects.filter(
            donor__email=donor_email, amount=5, recurring=True, method="paypal"
        ).latest("timestamp")
        assert donation.received_timestamp is None
        assert donation.payment.status != "pending"
        assert donation.payment.status != "confirmed"

        await page.locator('[data-test-id="continueButton"]').click()

        await page.wait_for_url(DONATION_DONE_URL)

        assert await page.get_by_text("Vielen Dank für Ihre Spende!").is_visible()
        assert await page.get_by_text(donor_email).is_visible()

        print("Waiting for webhooks...")

    await asyncio.sleep(2)
    donation.refresh_from_db()
    assert donation.completed is True
    assert donation.received_timestamp is not None
    payment = donation.payment
    assert donation.order.subscription_id is not None
    assert payment.status == "confirmed"

    subscription = donation.order.subscription
    sub_url = live_server.url + reverse(
        "froide_payment:subscription-detail", kwargs={"token": subscription.token}
    )
    old_plan = subscription.plan
    await page.goto(live_server.url + donation.donor.get_absolute_url())
    # Go to subscription url
    await page.goto(sub_url)
    await page.locator("#id_amount").fill("10")
    await page.locator("#id_interval_1").click()
    await page.get_by_role("button", name="Dauerspende ändern").click()

    await page.locator("input[type=submit]").click()
    await page.wait_for_load_state("networkidle")

    # Check subscription change
    subscription.refresh_from_db()
    assert subscription.plan != old_plan
    assert subscription.plan.amount == Decimal("10")
    assert subscription.plan.interval == 3


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.django_db
@pytest.mark.paypal
async def test_paypal_cancel(page: Page, live_server, paypal_setup):
    donor_email = "peter.parker@example.com"

    await page.goto(live_server.url + reverse("fds_donation:donate"))
    await page.get_by_role("button", name="5 Euro").click()
    await page.get_by_text("Paypal", exact=True).click()
    await fill_donation_page(page, donor_email)

    await page.get_by_role("button", name="Jetzt spenden").click()

    await login_paypal(page)
    await asyncio.sleep(2)

    donation = Donation.objects.filter(
        donor__email=donor_email, amount=5, recurring=False, method="paypal"
    ).latest("timestamp")
    assert donation.received_timestamp is None
    assert donation.payment.status != "pending"
    assert donation.payment.status != "confirmed"
    await page.locator("#cancelLink").click()

    await page.wait_for_url(DONATION_FAILED_URL)

    assert await page.get_by_text("Spende fehlgeschlagen!").is_visible()

    donation.refresh_from_db()
    assert donation.completed is False
    assert donation.received_timestamp is None
