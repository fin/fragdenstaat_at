import pytest
import pytest_asyncio
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


@pytest_asyncio.fixture(loop_scope="session")
async def page_diagnostics(page):
    """Record console output, JS errors and failed requests for a page.

    When a Playwright locator times out we learn only that an element was not
    visible. If the reason is that the JS which would have revealed it never
    ran -- bundle 404, syntax error, exception during init -- none of that
    appears anywhere. These listeners capture it so dump_page_state() can print
    it alongside the screenshot.
    """
    log = {"console": [], "pageerror": [], "requestfailed": [], "http_error": []}
    page.on("console", lambda m: log["console"].append(f"{m.type}: {m.text}"))
    page.on("pageerror", lambda e: log["pageerror"].append(str(e)))
    page.on(
        "requestfailed",
        lambda r: log["requestfailed"].append(f"{r.method} {r.url} :: {r.failure}"),
    )

    def _on_response(r):
        if r.status >= 400:
            log["http_error"].append(f"HTTP {r.status} {r.url}")

    page.on("response", _on_response)
    return log


async def dump_page_state(page, label, log=None, extra_selectors=()):
    """Write a screenshot and HTML, and print what the page was doing.

    Call from an except block; it re-raises nothing, so the original error
    still propagates.
    """
    import pathlib as _p
    import tempfile

    base = _p.Path(tempfile.gettempdir()) / f"dbg-{label}"
    try:
        await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
        base.with_suffix(".html").write_text(await page.content(), encoding="utf-8")
        print(f"\n  screenshot: {base.with_suffix('.png')}")
        print(f"  html      : {base.with_suffix('.html')}")
    except Exception as exc:  # pragma: no cover - diagnostics only
        print(f"\n  (could not capture page: {exc})")

    print(f"  url       : {page.url}")

    # Did the JS that should drive this page actually arrive and run?
    try:
        loaded = await page.evaluate(
            "() => Array.from(document.scripts).map(s => s.src).filter(Boolean)"
        )
        print("  scripts   :")
        for src in loaded:
            print(f"      {src}")
    except Exception:
        pass

    for sel in extra_selectors:
        try:
            el = page.locator(sel)
            count = await el.count()
            if not count:
                print(f"  {sel}: NOT IN DOM")
                continue
            print(
                f"  {sel}: count={count} "
                f"visible={await el.first.is_visible()} "
                f"hidden_attr={await el.first.get_attribute('hidden')!r}"
            )
        except Exception as exc:
            print(f"  {sel}: could not inspect ({exc})")

    if log:
        for key in ("pageerror", "requestfailed", "http_error", "console"):
            entries = log.get(key) or []
            if entries:
                print(f"  {key}:")
                for line in entries[-15:]:
                    print(f"      {line}")
