"""Deliberately FAILING tests that feed the triage demo (see README, "Triage evidence").

Excluded from normal runs. Run them with:   python -m pytest web/tests/test_triage_demo.py -m demo --clean-alluredir
Each one breaks something on purpose, in a different way, so the triage report shows different
verdicts. They are real failures: nothing here is skipped, retried or weakened.
"""

import allure
import pytest
from playwright.sync_api import Locator, Page, expect

from web.pages.dashboard_page import DashboardPage

pytestmark = pytest.mark.demo


class BrokenDashboardPage(DashboardPage):
    """The dashboard page object with one locator pointed at the wrong element, on purpose."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.wrong_greeting: Locator = page.get_by_text("Welcome Back Wrong,")  # does not exist
        self.missing_button: Locator = page.get_by_role("button", name="No Such Button")

    def validate_greeting_with_wrong_locator(self) -> None:
        expect(self.wrong_greeting).to_be_visible()

    def click_missing_button(self) -> None:
        self.missing_button.click(timeout=3_000)

    def validate_greeting_text(self, expected: str) -> None:
        expect(self.loc.greeting).to_have_text(expected)


@pytest.fixture
def broken_dashboard_page(page: Page) -> BrokenDashboardPage:
    return BrokenDashboardPage(page)


@allure.feature("Triage demo")
class TestTriageDemo:
    @allure.title("Demo: a locator pointing at the wrong element should fail with element not found")
    @allure.label("case_id", "WEB-01")
    def test_demo_a_locator_pointing_at_the_wrong_element_should_fail_with_element_not_found(
        self, broken_dashboard_page
    ):
        broken_dashboard_page.visit()
        broken_dashboard_page.is_ready()
        broken_dashboard_page.validate_greeting_with_wrong_locator()

    @allure.title("Demo: clicking a control that does not exist should fail with a timeout")
    @allure.label("case_id", "WEB-05")
    def test_demo_clicking_a_control_that_does_not_exist_should_fail_with_a_timeout(self, broken_dashboard_page):
        broken_dashboard_page.visit()
        broken_dashboard_page.is_ready()
        broken_dashboard_page.click_missing_button()

    @allure.title("Demo: asserting a greeting the test case never promised should fail on the value")
    @allure.label("case_id", "WEB-01")
    def test_demo_asserting_a_greeting_the_test_case_never_promised_should_fail_on_the_value(
        self, broken_dashboard_page
    ):
        broken_dashboard_page.visit()
        broken_dashboard_page.is_ready()
        broken_dashboard_page.validate_greeting_text("Selamat Datang,")  # WEB-01 promises "Welcome Back,"
