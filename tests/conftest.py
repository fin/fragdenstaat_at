import os

import pytest
import pytest_asyncio

from froide.account.factories import UserFactory

# Environment variables silently take priority over pytest.ini's
# DJANGO_SETTINGS_MODULE/DJANGO_CONFIGURATION (see pytest-django's
# _get_option_with_source), which previously caused a real misdiagnosis:
# the suite ran under the `Dev` configuration instead of `Test` and
# FIXTURE_DIRS appeared empty. Fail loudly instead of silently switching
# settings out from under whoever is running the suite.
_EXPECTED_DJANGO_ENV = {
    "DJANGO_SETTINGS_MODULE": "fragdenstaat_at.settings.test",
    "DJANGO_CONFIGURATION": "Test",
}


def pytest_configure(config):
    mismatched = {
        var: os.environ[var]
        for var, expected in _EXPECTED_DJANGO_ENV.items()
        if os.environ.get(var) not in (None, expected)
    }
    if mismatched:
        details = ", ".join(f"{var}={value!r}" for var, value in mismatched.items())
        pytest.exit(
            "Refusing to run: environment variable(s) override pytest.ini's "
            f"Django settings ({details}). Environment variables silently "
            "take priority over pytest.ini and change which Django settings "
            "module/configuration the suite actually runs under -- this "
            "previously caused a real misdiagnosis (the suite ran under the "
            "Dev configuration and FIXTURE_DIRS appeared empty). "
            "Run: env -u DJANGO_SETTINGS_MODULE -u DJANGO_CONFIGURATION ...",
            returncode=1,
        )


@pytest.fixture
def dummy_user():
    yield UserFactory(username="dummy")


@pytest.fixture()
def request_throttle_settings(settings):
    froide_config = settings.FROIDE_CONFIG
    froide_config["request_throttle"] = [(2, 60), (5, 60 * 60)]
    settings.FROIDE_CONFIG = froide_config


# Async to match pytest-playwright-asyncio (see pyproject.toml). Overrides the
# plugin's `page` only to pin locale="en", so a developer's browser locale cannot
# change which strings the assertions see.
@pytest_asyncio.fixture(loop_scope="session")
async def page(browser):
    context = await browser.new_context(locale="en")
    page = await context.new_page()
    yield page
    await page.close()
