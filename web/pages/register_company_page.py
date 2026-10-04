import re

import allure
from playwright.sync_api import Locator, Page, expect

from web.pages.base_page import BasePage


class RegisterCompanyLocators:
    def __init__(self, page: Page):
        self._page = page
        # Placeholders are the only stable hooks on the text inputs (no test ids / names).
        self.company_name_input: Locator = page.get_by_placeholder("Input Company Name")
        self.email_input: Locator = page.get_by_placeholder("Input Email")
        self.phone_input: Locator = page.get_by_placeholder("Input Phone")
        self.street_address_input: Locator = page.get_by_placeholder("Input Address")
        self.next_button: Locator = page.get_by_role("button", name="Next", exact=True)
        self.register_button: Locator = page.get_by_role("button", name="Register", exact=True)
        # Text locators on purpose: step titles are plain text without a role.
        self.step_one_title: Locator = page.get_by_text("Register Company", exact=True)
        self.step_one_counter: Locator = page.get_by_text("1/3", exact=True)
        self.step_two_title: Locator = page.get_by_text("Register Legal", exact=True)
        self.step_three_title: Locator = page.get_by_text("Create Your Branch", exact=True)
        self.policy_checkbox: Locator = page.get_by_role("checkbox")
        self.copy_company_data_button: Locator = page.get_by_role(
            "button", name="Fill in with the same data from the Company records")
        # Text locator on purpose: the inline validation message has no role or test id.
        self.invalid_email_error: Locator = page.get_by_text("Please provide a valid email address", exact=True)

    def combobox(self, label: str) -> Locator:
        """The dropdown under a field label.

        The dropdowns have generated ids and no accessible name. Each sits in a
        <div> whose direct child is the label <span>, so the label is the hook.
        """
        wrapper = self._page.locator(f"div:has(> span:text-matches('^{label}[*]?$'))")
        return wrapper.get_by_role("combobox")

    def option(self, value: str) -> Locator:
        return self._page.get_by_role("option", name=value, exact=True)


class RegisterCompanyPage(BasePage):
    page_path = "/companies/registration-companies"

    def __init__(self, page: Page):
        super().__init__(page)
        self.loc = RegisterCompanyLocators(page)

    def is_ready(self) -> None:
        expect(self.loc.step_one_title).to_be_visible()
        expect(self.loc.step_one_counter).to_be_visible()

    # --- actions: step 1 ---
    def fill_company_name(self, name: str) -> None:
        self.loc.company_name_input.fill(name)

    def fill_email(self, email: str) -> None:
        self.loc.email_input.fill(email)

    def fill_phone(self, phone: str) -> None:
        self.loc.phone_input.fill(phone)

    def fill_street_address(self, address: str) -> None:
        self.loc.street_address_input.fill(address)

    def select_option(self, label: str, value: str, search: bool = False) -> None:
        """Open the dropdown under `label` and pick `value` (type to filter long lists)."""
        self.loc.combobox(label).click()
        if search:
            self._page.keyboard.type(value)
        self.loc.option(value).click()

    def select_country(self, country: str) -> None:
        self.select_option("Country", country)

    def select_location(self, data: dict) -> None:
        """Province > City > District > Sub District, in order (each depends on the previous)."""
        self.select_option("Province", data["province"], search=True)
        self.select_option("City", data["city"], search=True)
        self.select_option("District", data["district"], search=True)
        self.select_option("Sub District", data["sub_district"], search=True)

    def click_next(self) -> None:
        self.loc.next_button.click()

    # --- flows ---
    def fill_step_one(self, data: dict) -> None:
        with allure.step("Fill Register Company (step 1)"):
            self.fill_company_name(data["name"])
            self.fill_email(data["email"])
            self.fill_phone(data["phone"])
            self.select_option("Industry Type", data["industry_type"])
            self.select_option("Company Type", data["company_type"])
            self.select_option("Language", data["language"])
            self.fill_street_address(data["street_address"])
            self.select_country(data["country"])
            self.select_location(data)
            self.validate_postal_code(data["postal_code"])  # auto-filled once the sub district is set
            self.log_event("Step 1 filled")

    def register_company(self, data: dict) -> None:
        """All three steps. Step 2 (optional legal document) and step 3 (optional branch)
        are left empty: the app then creates a default branch."""
        with allure.step(f"Register company '{data['name']}'"):
            self.fill_step_one(data)
            self.validate_next_enabled()
            self.click_next()
            expect(self.loc.step_two_title).to_be_visible()
            self.click_next()
            expect(self.loc.step_three_title).to_be_visible()
            # The branch form is optional ("a default branch will be created"), so it is left
            # empty. expect() before each click: if a control is missing, the failure carries
            # the page snapshot, which a bare click timeout does not.
            expect(self.loc.policy_checkbox).to_be_visible()
            self.loc.policy_checkbox.check()
            # Some app versions prefill the branch name ("Headquarter"); the form then insists on the
            # rest of the branch and keeps Register disabled. Copying the company data is the form's own way out.
            if self.loc.register_button.is_disabled():
                self.loc.copy_company_data_button.click()
            expect(self.loc.register_button).to_be_enabled()
            self.loc.register_button.click()
            expect(self._page).to_have_url(re.compile(r"/companies/?$"), timeout=60_000)
            self.log_event("Company registered")

    # --- assertions ---
    def validate_next_enabled(self) -> None:
        expect(self.loc.next_button).to_be_enabled()

    def validate_next_disabled(self) -> None:
        with allure.step("Next stays disabled"):
            expect(self.loc.next_button).to_be_disabled()

    def validate_still_on_step_one(self) -> None:
        with allure.step("Wizard stays on step 1"):
            expect(self.loc.step_one_counter).to_be_visible()
            expect(self.loc.step_two_title).to_have_count(0)

    def validate_invalid_email_error(self) -> None:
        with allure.step('Email field shows "Please provide a valid email address"'):
            expect(self.loc.invalid_email_error).to_be_visible()

    def validate_postal_code(self, postal_code: str) -> None:
        with allure.step(f"Postal code auto-filled with {postal_code}"):
            expect(self.loc.combobox("Postal Code")).to_have_text(postal_code)

    def validate_country_level_state(self) -> None:
        """Right after choosing Indonesia only Province is available."""
        with allure.step("Only Province is enabled below Country"):
            expect(self.loc.combobox("Province")).to_be_enabled()
            for label in ("City", "District", "Sub District", "Postal Code"):
                expect(self.loc.combobox(label)).to_be_disabled()

    def validate_province_level_state(self) -> None:
        with allure.step("City is enabled after Province; District and below are still disabled"):
            expect(self.loc.combobox("City")).to_be_enabled()
            for label in ("District", "Sub District", "Postal Code"):
                expect(self.loc.combobox(label)).to_be_disabled()

    def validate_lower_levels_cleared(self) -> None:
        with allure.step("Changing the province clears City, District, Sub District and Postal Code"):
            placeholders = {
                "City": "Choose City",
                "District": "Choose District",
                "Sub District": "Choose Sub District",
                "Postal Code": "Choose Postal Code",
            }
            for label, placeholder in placeholders.items():
                expect(self.loc.combobox(label)).to_have_text(placeholder)
