import re

import allure
from playwright.sync_api import Locator, Page, expect

from web.pages.base_page import BasePage

# The product shows a different dialog depending on what was typed.
UNREGISTERED_TITLE = "Username Not Registered"  # input without an @
UNREGISTERED_MESSAGE = "We could not find an account with that username. Please check your input and try again."
EMAIL_UNREGISTERED_TITLE = "Email Not Registered"  # input that is an email address
EMAIL_UNREGISTERED_MESSAGE = "You can continue by creating new account with this email"


class LoginLocators:
    """Every locator of the login journey lives here (one object per page)."""

    def __init__(self, page: Page):
        self.use_email_button: Locator = page.get_by_role("button", name="Use Email or Username")
        # No data-testid / name on the account-center inputs, and each screen shows a
        # single textbox, so role=textbox is the most stable hook available.
        self.email_input: Locator = page.get_by_role("textbox").first
        # type=password is a stable attribute; a password field has no ARIA role.
        self.password_input: Locator = page.locator("input[type='password']")
        # Submit label is not documented; match the labels the screens may use.
        self.submit_button: Locator = page.get_by_role(
            "button", name=re.compile(r"^(next|continue|log ?in|sign ?in|masuk|lanjut)", re.I)
        )
        # Text locators on purpose: the error banner / dialog expose no role or test id.
        # The banner ends with a per-request reference code, so only its prefix is stable.
        self.incorrect_password_error: Locator = page.get_by_text(re.compile(r"^Incorrect password"))
        self.unregistered_title: Locator = page.get_by_text(UNREGISTERED_TITLE, exact=True)
        self.unregistered_message: Locator = page.get_by_text(UNREGISTERED_MESSAGE, exact=True)
        self.email_unregistered_title: Locator = page.get_by_text(EMAIL_UNREGISTERED_TITLE, exact=True)
        self.email_unregistered_message: Locator = page.get_by_text(EMAIL_UNREGISTERED_MESSAGE, exact=True)
        self.edit_button: Locator = page.get_by_role("button", name="Edit")
        self.register_button: Locator = page.get_by_role("button", name="Yes, Register")
        self._page = page

    def entered_value(self, value: str) -> Locator:
        """The username echoed back inside the 'Username Not Registered' dialog."""
        return self._page.get_by_text(value, exact=True)


class LoginPage(BasePage):
    """eSuite sign-in: three screens, redirected through the eDOT Account Center.

    1. "Use Email or Username"  2. email  3. password. The account center is
    another origin, so every wait is expect() auto-waiting - no sleeps.
    """

    page_path = "/"

    def __init__(self, page: Page):
        super().__init__(page)
        self.loc = LoginLocators(page)

    def is_ready(self) -> None:
        expect(self.loc.use_email_button).to_be_visible()

    # --- actions ---
    def click_use_email_option(self) -> None:
        self.loc.use_email_button.click()

    def fill_email(self, email: str) -> None:
        expect(self.loc.email_input).to_be_visible()
        self.loc.email_input.fill(email)

    def fill_password(self, password: str) -> None:
        expect(self.loc.password_input).to_be_visible()
        self.loc.password_input.fill(password)

    def click_submit(self) -> None:
        self.loc.submit_button.click()

    # --- flows ---
    def submit_email_only(self, email: str) -> None:
        """Go through screens 1 and 2 and stop after submitting the email."""
        with allure.step(f"Submit email/username '{email}'"):
            self.visit()
            self.is_ready()
            self.click_use_email_option()
            self.fill_email(email)
            self.click_submit()

    def attempt_login(self, email: str, password: str) -> None:
        with allure.step("Submit email, then password"):
            self.submit_email_only(email)
            self.fill_password(password)
            self.click_submit()
            self.log_event("Submitted credentials")

    def perform_valid_login(self, email: str, password: str) -> None:
        with allure.step("Log in to eSuite"):
            self.attempt_login(email, password)

    # --- assertions ---
    def validate_incorrect_password_error(self) -> None:
        with allure.step('Banner shows "Incorrect password"'):
            expect(self.loc.incorrect_password_error).to_be_visible()
            expect(self.loc.incorrect_password_error).to_contain_text("Incorrect password")

    def validate_email_not_registered(self, email: str) -> None:
        with allure.step("Dialog says the email is not registered"):
            expect(self.loc.email_unregistered_title).to_be_visible()
            expect(self.loc.email_unregistered_message).to_be_visible()
            expect(self.loc.entered_value(email)).to_be_visible()  # echoes what was typed
            expect(self.loc.edit_button).to_be_visible()
            expect(self.loc.register_button).to_be_visible()

    def validate_username_not_registered(self, username: str) -> None:
        with allure.step("Dialog says the username is not registered"):
            expect(self.loc.unregistered_title).to_be_visible()
            expect(self.loc.unregistered_message).to_be_visible()
            expect(self.loc.entered_value(username)).to_be_visible()  # echoes what was typed
            expect(self.loc.edit_button).to_be_visible()

    def validate_submit_disabled(self) -> None:
        with allure.step("Log In stays disabled"):
            expect(self.loc.submit_button).to_be_disabled()
