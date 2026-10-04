import allure
import pytest


@pytest.fixture(scope="module")
def saved():
    """Set by MOB-03 once the customer exists, read by MOB-04."""
    return {"created": False}


@allure.feature("Mobile new customer")
@pytest.mark.mobile
class TestMobileNewCustomer:
    # Order matters: MOB-03 saves the customer on the device first, MOB-04 reads it back in the same
    # session, and MOB-05 logs in again (which clears the app data), so it must run last.

    @allure.title("Mobile create customer with valid data should list the new customer")
    @allure.label("case_id", "MOB-03")
    @pytest.mark.tier2
    def test_mobile_create_customer_with_valid_data_should_list_the_new_customer(self, run_flow, customer, saved):
        run_flow("create_customer.yaml", **customer)  # Tier 2: the flow ends on the customer in the list
        saved["created"] = True

    @allure.title("Mobile customer card should show the data that was entered")
    @allure.label("case_id", "MOB-04")
    @pytest.mark.tier2
    def test_mobile_customer_card_should_show_the_data_that_was_entered(self, run_flow, customer, saved):
        if not saved["created"]:
            pytest.fail("Precondition failed: MOB-03 did not create the customer")
        run_flow("verify_customer_card.yaml", **customer)

    @allure.title("Mobile create customer without an outlet name should keep Continue disabled")
    @allure.label("case_id", "MOB-05")
    @pytest.mark.negative
    def test_mobile_create_customer_without_an_outlet_name_should_keep_continue_disabled(self, run_flow, customer):
        run_flow("create_customer_without_name.yaml", **customer)
