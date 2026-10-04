import allure
import pytest

WRONG_PASSWORD = "Wrong#Pass123"  # deliberately wrong, not a secret


@allure.feature("Mobile login")
@pytest.mark.mobile
class TestMobileLogin:
    @allure.title("Mobile login with valid credentials should show the dashboard")
    @allure.label("case_id", "MOB-01")
    @pytest.mark.tier1
    def test_mobile_login_with_valid_credentials_should_show_the_dashboard(self, run_flow):
        run_flow("login_success.yaml")  # Tier 1: the flow asserts the dashboard is visible

    @allure.title("Mobile login with a wrong password should show the wrong login combination error")
    @allure.label("case_id", "MOB-02")
    @pytest.mark.negative
    def test_mobile_login_with_a_wrong_password_should_show_the_wrong_login_combination_error(self, run_flow):
        run_flow("login_wrong_password.yaml", PASSWORD=WRONG_PASSWORD)
