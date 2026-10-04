import re

import allure
from playwright.sync_api import Locator, Page, expect

from web.pages.base_page import NAVIGATION_TIMEOUT, BasePage


class CompanyDetailLocators:
    def __init__(self, page: Page):
        self._page = page
        self.heading: Locator = page.get_by_role("heading", name="Company Details")
        self.delete_button: Locator = page.get_by_role("button", name="Delete", exact=True)
        self.company_name_input: Locator = page.get_by_placeholder("Input Company Name")
        self.company_id_input: Locator = page.get_by_placeholder("Input Company ID")
        self.email_input: Locator = page.get_by_placeholder("Input Email")
        self.mobile_input: Locator = page.get_by_placeholder("Input Mobile Number")
        self.address_textarea: Locator = page.get_by_placeholder("Input Company Address")
        # Delete confirmation ("Confirmation Delete"): a modal with a checkbox gate.
        self.confirm_dialog: Locator = page.get_by_role("dialog")
        # Text locator on purpose: the success toast has no role/test id; wording differs
        # slightly from the spec ("company delete successfully"), so match the meaning.
        self.delete_toast: Locator = page.get_by_text(re.compile(r"delet.*success|success.*delet", re.I))

    def combobox(self, label: str) -> Locator:
        """Same label-span structure as the registration form."""
        wrapper = self._page.locator(f"div:has(> span:text-matches('^{label}[*]?$'))")
        return wrapper.get_by_role("combobox")


class CompanyDetailPage(BasePage):
    page_path = "/companies/manage-companies"

    def __init__(self, page: Page):
        super().__init__(page)
        self.loc = CompanyDetailLocators(page)

    def is_ready(self) -> None:
        expect(self._page).to_have_url(re.compile(r"/companies/manage-companies/.+/profile"), timeout=NAVIGATION_TIMEOUT)
        expect(self.loc.heading).to_be_visible()
        expect(self.loc.delete_button).to_be_visible()

    def company_id(self) -> str:
        """The company id travels in the URL (?cid=...)."""
        match = re.search(r"cid=(\d+)", self._page.url)
        assert match, f"no cid in URL {self._page.url}"
        return match.group(1)

    def wait_until_loaded(self, attempts: int = 4) -> None:
        """A brand-new company's form can stay blank for a while. Reload a few times; if the
        form is still blank after the last attempt, the assertion error is raised as usual."""
        with allure.step("Wait for the company form to be populated"):
            for attempt in range(attempts):
                try:
                    expect(self.loc.company_name_input).not_to_have_value("", timeout=15_000)
                    return
                except AssertionError:
                    if attempt == attempts - 1:
                        raise
                    self._page.reload()

    # --- assertions ---
    def validate_company_details(self, data: dict) -> None:
        """Field-by-field comparison with what was entered (each field asserted on its own)."""
        with allure.step("Detail view matches the entered data"):
            # Tier 2: every value below must equal the input; a mismatch is a product bug
            expect(self.loc.company_name_input, "Company Name").to_have_value(data["name"])
            expect(self.loc.combobox("Industry Type"), "Industry Type").to_have_text(data["industry_type"])
            expect(self.loc.combobox("Company Type"), "Company Type").to_have_text(data["company_type"])
            expect(self.loc.address_textarea, "Street Address").to_have_value(data["street_address"])
            expect(self.loc.combobox("Country"), "Country").to_have_text(data["country"])
            expect(self.loc.combobox("Province"), "Province").to_have_text(data["province"])
            expect(self.loc.combobox("City"), "City").to_have_text(data["city"])
            expect(self.loc.combobox("District"), "District").to_have_text(data["district"])
            expect(self.loc.combobox("Sub District"), "Sub District").to_have_text(data["sub_district"])
            expect(self.loc.combobox("Postal Code"), "Postal Code").to_have_text(data["postal_code"])
            expect(self.loc.email_input, "Email").to_have_value(data["email"])
            expect(self.loc.mobile_input, "Phone").to_have_value(data["phone"])

    def validate_company_id(self, company_id: str) -> None:
        expect(self.loc.company_id_input).to_have_value(company_id)

    def validate_delete_toast(self) -> None:
        with allure.step("A delete-success toast is shown"):
            expect(self.loc.delete_toast).to_be_visible()

    # --- flows ---
    def delete_company(self) -> None:
        """Delete through the UI: Delete > tick 'I understand & agree to delete' > Confirm."""
        with allure.step("Delete the company"):
            self.loc.delete_button.click()
            expect(self.loc.confirm_dialog).to_be_visible()
            self.loc.confirm_dialog.get_by_role("checkbox").check()
            self.loc.confirm_dialog.get_by_role("button", name="Confirm", exact=True).click()
            self.validate_delete_toast()
            self.log_event("Company deleted")
