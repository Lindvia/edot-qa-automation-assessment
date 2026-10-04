import allure
from playwright.sync_api import Locator, Page, expect

from web.pages.base_page import BasePage


class DashboardLocators:
    def __init__(self, page: Page):
        # Text locator on purpose: the brief defines the greeting by its text
        # ("Welcome Back,") and the element has no role or test id.
        self.greeting: Locator = page.get_by_text("Welcome Back,")
        self.companies_link: Locator = page.get_by_role("link", name="Companies")


class DashboardPage(BasePage):
    page_path = "/"

    def __init__(self, page: Page):
        super().__init__(page)
        self.loc = DashboardLocators(page)

    def is_ready(self) -> None:
        expect(self.loc.greeting).to_be_visible()
        expect(self.loc.companies_link).to_be_visible()

    # --- actions ---
    def click_companies(self) -> None:
        with allure.step("Open Companies"):
            self.loc.companies_link.click()

    # --- assertions ---
    def validate_welcome_greeting(self) -> None:
        with allure.step('Dashboard shows the "Welcome Back," greeting'):
            expect(self.loc.greeting).to_be_visible()  # Tier 1: display only
