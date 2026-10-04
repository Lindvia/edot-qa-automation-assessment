"""Registers every page object as a pytest fixture (the pages/index.ts of the
provider suite). Specs never construct a page object - they ask for one:

    def test_x(dashboard_page): ...

Add a new page object here (one fixture per class) so it is injectable.
"""

import pytest
from playwright.sync_api import Page

from config import settings
from web.pages.companies_page import CompaniesPage
from web.pages.company_detail_page import CompanyDetailPage
from web.pages.dashboard_page import DashboardPage
from web.pages.login_page import LoginPage
from web.pages.register_company_page import RegisterCompanyPage


@pytest.fixture
def login_page(page: Page) -> LoginPage:
    return LoginPage(page)


@pytest.fixture
def dashboard_page(page: Page) -> DashboardPage:
    return DashboardPage(page)


@pytest.fixture
def companies_page(page: Page) -> CompaniesPage:
    return CompaniesPage(page)


@pytest.fixture
def register_company_page(page: Page) -> RegisterCompanyPage:
    return RegisterCompanyPage(page)


@pytest.fixture
def company_detail_page(page: Page) -> CompanyDetailPage:
    return CompanyDetailPage(page)


@pytest.fixture
def anonymous_page(browser):
    """A page in a fresh context with NO saved session (for login negatives)."""
    context = browser.new_context(base_url=settings.ESUITE_URL)
    yield context.new_page()
    context.close()


@pytest.fixture
def anonymous_login_page(anonymous_page: Page) -> LoginPage:
    return LoginPage(anonymous_page)
