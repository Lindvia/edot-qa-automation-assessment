"""Create > verify > delete one company. The three tests run in this order and share one
record. Whatever happens, the module teardown deletes the company so the shared
environment is left clean."""

from dataclasses import dataclass
from typing import Optional

import allure
import pytest

from ai.data_generator import attach_to_allure, generate_company
from config import settings
from web.pages.companies_page import CompaniesPage
from web.pages.company_detail_page import CompanyDetailPage


@dataclass
class CreatedCompany:
    data: Optional[dict] = None
    created: bool = False
    deleted: bool = False
    company_id: Optional[str] = None


@pytest.fixture(scope="module")
def created_company() -> CreatedCompany:
    return CreatedCompany()


@pytest.fixture(scope="module", autouse=True)
def cleanup_company(browser, auth_state, created_company):
    """Delete the company at the end of the run, even if a test failed half way."""
    yield
    if created_company.data is None or created_company.deleted:
        return
    name = created_company.data["name"]
    context = browser.new_context(storage_state=auth_state, base_url=settings.ESUITE_URL)
    try:
        page = context.new_page()
        companies = CompaniesPage(page)
        companies.visit()
        companies.is_ready()
        if companies.is_listed(name):
            companies.click_manage(name)
            detail = CompanyDetailPage(page)
            detail.is_ready()
            detail.delete_company()
    finally:
        context.close()


@pytest.fixture
def existing_company(created_company) -> CreatedCompany:
    if not created_company.created:
        pytest.fail("Precondition failed: the company was not created by the previous test")
    return created_company


@allure.feature("Companies")
class TestCompanyLifecycle:
    @allure.title("Registering a company with valid data should list it as an Active company")
    @allure.label("case_id", "WEB-08")
    @pytest.mark.tier2
    def test_registering_a_company_with_valid_data_should_list_it_as_an_active_company(
        self, register_company_page, companies_page, created_company
    ):
        result = generate_company()
        attach_to_allure(result, "Generated company data")
        data = result.data
        created_company.data = data  # recorded first so teardown can clean up a half-created company

        register_company_page.visit()
        register_company_page.is_ready()
        register_company_page.register_company(data)

        companies_page.is_ready()
        companies_page.validate_company_listed(data["name"])
        created_company.created = True

    @allure.title("Company detail should show exactly the data that was entered")
    @allure.label("case_id", "WEB-09")
    @pytest.mark.tier2
    def test_company_detail_should_show_exactly_the_data_that_was_entered(
        self, companies_page, company_detail_page, existing_company
    ):
        data = existing_company.data
        companies_page.visit()
        companies_page.is_ready()
        companies_page.click_manage(data["name"])
        companies_page.validate_manage_url()

        company_detail_page.is_ready()
        company_detail_page.wait_until_loaded()
        existing_company.company_id = company_detail_page.company_id()
        company_detail_page.validate_company_details(data)
        company_detail_page.validate_company_id(existing_company.company_id)

    @allure.title("Deleting the company should show a success toast, remove it from the list and log the deletion")
    @allure.label("case_id", "WEB-12")
    @pytest.mark.tier2
    def test_deleting_the_company_should_show_a_success_toast_remove_it_from_the_list_and_log_the_deletion(
        self, companies_page, company_detail_page, existing_company
    ):
        name = existing_company.data["name"]
        companies_page.visit()
        companies_page.is_ready()
        companies_page.click_manage(name)

        company_detail_page.is_ready()
        company_detail_page.delete_company()

        companies_page.visit()
        companies_page.is_ready()
        companies_page.validate_company_not_listed(name)
        # Only now is the company known to be gone; until then the teardown still retries the delete.
        existing_company.deleted = True

        companies_page.click_log_activity()
        companies_page.validate_deletion_logged(name)
