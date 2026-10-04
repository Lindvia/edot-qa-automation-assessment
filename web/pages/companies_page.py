import re
import time

import allure
from playwright.sync_api import Locator, Page, expect

from config import settings
from web.pages.base_page import NAVIGATION_TIMEOUT, BasePage

LIST_TIMEOUT = 30_000  # the account lists several hundred companies
STABLE_FOR = 3_000     # a list that does not change for this long is fully loaded


class CompaniesLocators:
    def __init__(self, page: Page):
        self._page = page
        # Text locators on purpose: heading / banner text has no role or test id.
        self.heading: Locator = page.get_by_text("My Company", exact=True)
        self.loading: Locator = page.get_by_text("Please wait...")
        self.add_company_button: Locator = page.get_by_role("button", name="+ Add Company")
        self.log_activity_tab: Locator = page.get_by_role("tab", name="Log Activity")
        # exact=True keeps "Manage Company" (the header button) out of the card buttons.
        self.manage_buttons: Locator = page.get_by_role("button", name="Manage", exact=True)
        self.first_card_manage_button: Locator = self.manage_buttons.first

    def company_name(self, name: str) -> Locator:
        """The company name text on its card (appears once per company)."""
        return self._page.get_by_text(name, exact=True)

    def deleted_log_entry(self, name: str) -> Locator:
        """Log Activity row: Deleted "<name>" (the app wraps the name in curly quotes).

        Text locator on purpose: the log is a plain table with no roles or test ids.
        """
        return self._page.get_by_text(re.compile(rf"Deleted\s+[\"“”']?{re.escape(name)}[\"“”']?"))

    def company_card(self, name: str) -> Locator:
        """The smallest block holding both the name and a Manage button = that company's card."""
        return (
            self._page.locator("div")
            .filter(has_text=name)
            .filter(has=self._page.get_by_role("button", name="Manage", exact=True))
            .last
        )


class CompaniesPage(BasePage):
    page_path = "/companies"

    def __init__(self, page: Page):
        super().__init__(page)
        self.loc = CompaniesLocators(page)

    def is_ready(self) -> None:
        expect(self.loc.heading).to_be_visible()
        expect(self.loc.add_company_button).to_be_visible()

    def wait_for_list(self) -> None:
        """The list loads after the heading; wait for it before counting cards."""
        expect(self.loc.loading).to_have_count(0, timeout=LIST_TIMEOUT)
        expect(self.loc.first_card_manage_button).to_be_visible(timeout=LIST_TIMEOUT)

    def wait_for_full_list(self) -> int:
        """Wait until the list has stopped growing and return how many companies it holds.

        The list renders in batches: right after the first card appears, a company further down can
        still be missing, so "not listed" is only meaningful once the count stays the same for a while.
        A count that does not change for STABLE_FOR ms is taken as complete (auto-waiting, no sleep).
        """
        self.wait_for_list()
        count = self.loc.manage_buttons.count()
        while True:
            try:
                expect(self.loc.manage_buttons).not_to_have_count(count, timeout=STABLE_FOR)
            except AssertionError:
                return count  # unchanged for STABLE_FOR ms: the list is complete
            count = self.loc.manage_buttons.count()

    # --- actions ---
    def click_add_company(self) -> None:
        with allure.step("Click + Add Company"):
            self.loc.add_company_button.click()

    def click_manage(self, name: str) -> None:
        with allure.step(f"Open Manage for '{name}'"):
            self.loc.company_card(name).get_by_role("button", name="Manage", exact=True).click()

    def click_log_activity(self) -> None:
        with allure.step("Open the Log Activity tab"):
            self.loc.log_activity_tab.click()

    def is_listed(self, name: str) -> bool:
        self.wait_for_full_list()
        return self.loc.company_name(name).count() > 0

    # --- assertions ---
    def validate_page_elements(self) -> None:
        # Only what the test case promises: heading, Add Company button and the company list.
        # The header's extra buttons / tabs differ between app versions, so they are not asserted.
        with allure.step("Companies page shows its heading, Add Company button and company list"):
            expect(self.loc.heading).to_be_visible()  # Tier 1: display only
            expect(self.loc.add_company_button).to_be_visible()
            self.wait_for_list()

    def validate_company_listed(self, name: str) -> None:
        with allure.step(f"Company '{name}' is listed once and Active"):
            self.wait_for_list()
            # Tier 2: the record exists (exactly one card with this name), not just a toast
            expect(self.loc.company_name(name)).to_have_count(1, timeout=LIST_TIMEOUT)
            expect(self.loc.company_card(name).get_by_text("Active", exact=True)).to_be_visible()

    def validate_company_not_listed(self, name: str, timeout_s: int = settings.DELETE_WAIT_SECONDS) -> None:
        """The company must disappear from the list.

        The app removes a deleted company from the list asynchronously (the success toast
        appears at once, the card can stay for a while). So the list is reloaded until a
        time budget runs out; a company that is still listed after the budget fails.
        The measured delay is attached to the report.
        """
        with allure.step(f"Company '{name}' is gone from the list (waits up to {timeout_s}s)"):
            started = time.monotonic()
            while True:
                self.wait_for_full_list()
                elapsed = time.monotonic() - started
                if self.loc.company_name(name).count() == 0:
                    allure.attach(f"Removed from the list after {elapsed:.0f}s", name="delete-propagation",
                                  attachment_type=allure.attachment_type.TEXT)
                    return
                if elapsed >= timeout_s:
                    break
                self._page.reload()  # each reload + list load takes seconds; no sleep needed
            allure.attach(f"Still listed after {elapsed:.0f}s", name="delete-propagation",
                          attachment_type=allure.attachment_type.TEXT)
            # Tier 2: after a delete the record must be gone (fails with the evidence if not)
            expect(self.loc.company_name(name)).to_have_count(0)

    def validate_deletion_logged(self, name: str) -> None:
        with allure.step(f"Log Activity records the deletion of '{name}'"):
            # Tier 2: the audit trail independently confirms the delete happened
            expect(self.loc.deleted_log_entry(name)).to_be_visible(timeout=15_000)

    def validate_manage_url(self) -> None:
        expect(self._page).to_have_url(re.compile(r"/companies/manage-companies/"), timeout=NAVIGATION_TIMEOUT)
