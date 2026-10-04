import allure
import pytest

from config import settings

WRONG_PASSWORD = "Wrong#Pass123"  # deliberately wrong, not a secret
UNKNOWN_EMAIL = "no.such.user.qa@edot.id"
UNKNOWN_USERNAME = "nosuchuserqa"  # no @, so the product treats it as a username


@allure.feature("Login")
@pytest.mark.negative
class TestLoginNegative:
    # These run in a fresh context (anonymous_*), never with the saved session.

    @allure.title("Login with a wrong password should show the incorrect password error")
    @allure.label("case_id", "WEB-02")
    def test_login_with_a_wrong_password_should_show_the_incorrect_password_error(self, anonymous_login_page):
        email = settings.require("ESUITE_EMAIL", settings.ESUITE_EMAIL)
        anonymous_login_page.attempt_login(email, WRONG_PASSWORD)
        anonymous_login_page.validate_incorrect_password_error()

    @allure.title("Login with an unregistered email should show the email not registered dialog")
    @allure.label("case_id", "WEB-03")
    def test_login_with_an_unregistered_email_should_show_the_email_not_registered_dialog(
        self, anonymous_login_page
    ):
        anonymous_login_page.submit_email_only(UNKNOWN_EMAIL)
        anonymous_login_page.validate_email_not_registered(UNKNOWN_EMAIL)

    @allure.title("Login with an unregistered username should show the username not registered dialog")
    @allure.label("case_id", "WEB-13")
    def test_login_with_an_unregistered_username_should_show_the_username_not_registered_dialog(
        self, anonymous_login_page
    ):
        anonymous_login_page.submit_email_only(UNKNOWN_USERNAME)
        anonymous_login_page.validate_username_not_registered(UNKNOWN_USERNAME)

    @allure.title("Login with an empty email should keep the login button disabled")
    @allure.label("case_id", "WEB-04")
    def test_login_with_an_empty_email_should_keep_the_login_button_disabled(self, anonymous_login_page):
        anonymous_login_page.visit()
        anonymous_login_page.is_ready()
        anonymous_login_page.click_use_email_option()
        anonymous_login_page.validate_submit_disabled()
