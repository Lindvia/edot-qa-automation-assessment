import allure
import pytest

from ai import schemas

LOCATION = schemas.LOCATIONS[0]
OTHER_PROVINCE = "JAWA BARAT"


@allure.feature("Companies")
class TestCompanies:
    @allure.title("Companies page should show its heading, Add Company button and company list")
    @allure.label("case_id", "WEB-05")
    @pytest.mark.tier1
    def test_companies_page_should_show_its_heading_add_company_button_and_company_list(
        self, dashboard_page, companies_page
    ):
        dashboard_page.visit()
        dashboard_page.is_ready()
        dashboard_page.click_companies()
        companies_page.is_ready()
        companies_page.validate_page_elements()

    @allure.title("Add Company should open the Register Company wizard with Next disabled")
    @allure.label("case_id", "WEB-06")
    @pytest.mark.tier1
    def test_add_company_should_open_the_register_company_wizard_with_next_disabled(
        self, companies_page, register_company_page
    ):
        companies_page.visit()
        companies_page.is_ready()
        companies_page.click_add_company()
        register_company_page.is_ready()
        register_company_page.validate_next_disabled()

    @allure.title("Address fields should become available level by level and reset when the province changes")
    @allure.label("case_id", "WEB-07")
    @pytest.mark.tier1
    def test_address_fields_should_become_available_level_by_level_and_reset_when_the_province_changes(
        self, register_company_page
    ):
        register_company_page.visit()
        register_company_page.is_ready()

        register_company_page.select_country(LOCATION["country"])
        register_company_page.validate_country_level_state()

        register_company_page.select_option("Province", LOCATION["province"], search=True)
        register_company_page.validate_province_level_state()

        register_company_page.select_option("City", LOCATION["city"], search=True)
        register_company_page.select_option("District", LOCATION["district"], search=True)
        register_company_page.select_option("Sub District", LOCATION["sub_district"], search=True)
        register_company_page.validate_postal_code(LOCATION["postal_code"])

        register_company_page.select_option("Province", OTHER_PROVINCE, search=True)
        register_company_page.validate_lower_levels_cleared()

    @allure.title("Wizard should show the invalid email error when the email is malformed")
    @allure.label("case_id", "WEB-10")
    @pytest.mark.negative
    def test_wizard_should_show_the_invalid_email_error_when_the_email_is_malformed(
        self, register_company_page, company_data
    ):
        register_company_page.visit()
        register_company_page.is_ready()
        register_company_page.fill_step_one(company_data)
        register_company_page.fill_email("nusantara.example.co.id")  # no @
        register_company_page.click_next()
        register_company_page.validate_invalid_email_error()
        register_company_page.validate_still_on_step_one()  # the invalid email must not let the wizard advance

    @allure.title("Wizard should keep Next disabled when the company name is empty")
    @allure.label("case_id", "WEB-11")
    @pytest.mark.negative
    def test_wizard_should_keep_next_disabled_when_the_company_name_is_empty(
        self, register_company_page, company_data
    ):
        register_company_page.visit()
        register_company_page.is_ready()
        register_company_page.fill_step_one(company_data)
        register_company_page.validate_next_enabled()
        register_company_page.fill_company_name("")
        register_company_page.validate_next_disabled()
