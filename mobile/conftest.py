import re
import warnings
from typing import Callable, Dict

import pytest

from ai import schemas
from ai.data_generator import attach_to_allure, generate_customer
from config import settings
from mobile.maestro_runner import FlowResult, clear_app_session, run_flow as run_maestro_flow
from utils.helpers import generate_ktp_number


def tail(text: str, lines: int = 25) -> str:
    return "\n".join(text.splitlines()[-lines:])


def customer_env(data: dict) -> Dict[str, str]:
    """Flow variables for one customer. Maestro reads a selector text as a regex, so values that are
    only ever used as a selector and can contain regex characters (the channel has brackets) are
    escaped; free text typed into a field stays literal."""
    location = schemas.LOCATIONS[0]
    options = schemas.CUSTOMER_OPTIONS
    return {
        "OUTLET_NAME": data["outlet_name"],
        "PHONE": data["phone"],
        "EMAIL": data["email"],
        "CONTACT_PERSON": data["contact_person"],
        "STREET_ADDRESS": data["street_address"],
        "CHANNEL": re.escape(options["channel"]),
        "CUSTOMER_TYPE": options["customer_type"],
        "ADDRESS_TYPE": options["address_type"],
        "PROVINCE": location["province"],
        "CITY": location["city"],
        "DISTRICT": location["district"],
        "SUB_DISTRICT": location["sub_district"],
        "POSTAL_CODE": location["postal_code"],
        "KTP": generate_ktp_number(),
    }


@pytest.fixture(scope="module")
def customer() -> Dict[str, str]:
    """One generated customer shared by the customer tests of a module (AI data, Faker fallback)."""
    generated = generate_customer()
    attach_to_allure(generated, "customer-test-data")
    return customer_env(generated.data)


@pytest.fixture(scope="session")
def mobile_env() -> dict:
    """Credentials and app id for the flows, from the environment (never from a file in the repo)."""
    return {
        "APP_ID": settings.require("MOBILE_APP_ID", settings.MOBILE_APP_ID),
        "COMPANY_ID": settings.require("MOBILE_COMPANY_ID", settings.MOBILE_COMPANY_ID),
        "USERNAME": settings.require("MOBILE_USERNAME", settings.MOBILE_USERNAME),
        "PASSWORD": settings.require("MOBILE_PASSWORD", settings.MOBILE_PASSWORD),
    }


@pytest.fixture(scope="session", autouse=True)
def logged_out_at_the_end(mobile_env):
    """Whatever happened in the session (even failures), leave the app logged out when it ends.

    Once per session and not per test on purpose: a new customer is saved on the device first, so
    MOB-04 reads back what MOB-03 created and a logout in between would erase it."""
    yield
    if not clear_app_session(mobile_env["APP_ID"]):
        warnings.warn("eWork was NOT logged out at the end of the session (adb missing or the phone did not "
                      "answer): clear it by hand with `adb shell pm clear <app id>`.")


@pytest.fixture
def run_flow(mobile_env) -> Callable[..., FlowResult]:
    """Run a flow and fail the test (with Maestro's own output) if Maestro reports a failure.

    The assertions live in the YAML (assertVisible / assertNotVisible); this wrapper only turns a
    failed flow into a failed Pytest test and attaches the evidence. It never retries or ignores it.
    """

    def run(flow_name: str, **overrides: str) -> FlowResult:
        env = {**mobile_env, **overrides}
        result = run_maestro_flow(flow_name, env, settings.MAESTRO_CMD, settings.MOBILE_FLOW_TIMEOUT,
                                  settings.MOBILE_RECORD)
        assert result.passed, f"Maestro flow {flow_name} failed (exit {result.returncode}):\n{tail(result.output)}"
        return result

    return run
