import allure
import pytest
from playwright.sync_api import expect

from ai.data_generator import attach_to_allure, generate_company
from config import settings
from web.pages.dashboard_page import DashboardPage
from web.pages.fixtures import (  # noqa: F401  (register page fixtures)
    anonymous_login_page,
    anonymous_page,
    companies_page,
    company_detail_page,
    dashboard_page,
    login_page,
    register_company_page,
)
from web.pages.login_page import LoginPage

LOGIN_REDIRECT_TIMEOUT_MS = 60_000

expect.set_options(timeout=settings.EXPECT_TIMEOUT_MS)


@pytest.fixture
def company_data() -> dict:
    """AI-generated (schema-validated, Faker fallback) company data, attached to the report."""
    result = generate_company()
    attach_to_allure(result, "Generated company data")
    return result.data


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {**browser_type_launch_args, "headless": settings.HEADLESS}


@pytest.fixture(scope="session")
def auth_state(browser) -> str:
    """Log in through the UI once per session and save the session to disk.

    Every other test reuses this storage_state, so no test logs in again.
    The login itself is asserted here: if the dashboard does not appear the
    whole session fails loudly instead of every test timing out.
    """
    email = settings.require("ESUITE_EMAIL", settings.ESUITE_EMAIL)
    password = settings.require("ESUITE_PASSWORD", settings.ESUITE_PASSWORD)

    settings.AUTH_DIR.mkdir(exist_ok=True)
    context = browser.new_context(base_url=settings.ESUITE_URL)
    page = context.new_page()
    try:
        LoginPage(page).perform_valid_login(email, password)
        dashboard = DashboardPage(page)
        # The sign-in ends with an OIDC token redirect that took more than the default 5 s on a CI
        # runner (it stayed on "REDIRECTING..."); wait for it once here, the checks below then pass at once.
        expect(dashboard.loc.greeting).to_be_visible(timeout=LOGIN_REDIRECT_TIMEOUT_MS)
        dashboard.is_ready()
        dashboard.validate_welcome_greeting()
        context.storage_state(path=str(settings.STORAGE_STATE))
    except Exception:
        allure.attach(page.screenshot(full_page=True), name="login-failure",
                      attachment_type=allure.attachment_type.PNG)
        raise
    finally:
        context.close()
    return str(settings.STORAGE_STATE)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, auth_state):
    return {**browser_context_args, "storage_state": auth_state, "base_url": settings.ESUITE_URL}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """On a failed test body, attach a screenshot of the page it used to Allure.

    Done here (not in a fixture teardown) because this runs right after the test
    body, while the browser page is still open - a teardown can run after the
    page fixture has already been closed.
    """
    outcome = yield
    report = outcome.get_result()
    if call.when != "call" or not report.failed:
        return
    page = item.funcargs.get("anonymous_page") or item.funcargs.get("page")
    if page is None:
        return
    try:
        allure.attach(page.screenshot(full_page=True), name="failure-screenshot",
                      attachment_type=allure.attachment_type.PNG)
    except Exception as error:  # noqa: BLE001 - a missing screenshot must never hide the real failure
        allure.attach(str(error), name="failure-screenshot-error", attachment_type=allure.attachment_type.TEXT)
