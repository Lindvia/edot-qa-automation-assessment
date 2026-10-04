import allure
import pytest


@allure.feature("Login")
class TestLogin:
    # The UI login ran once in the session-scoped auth_state fixture; specs get
    # page objects as fixtures and never construct them.

    @allure.title("Login with valid credentials should show the dashboard greeting")
    @allure.label("case_id", "WEB-01")
    @pytest.mark.smoke
    @pytest.mark.tier1
    def test_login_with_valid_credentials_should_show_the_dashboard_greeting(self, dashboard_page):
        dashboard_page.visit()
        dashboard_page.is_ready()
        dashboard_page.validate_welcome_greeting()
