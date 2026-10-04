"""Offline tests for the mobile test data (no device, network or API key)."""

import re

from ai import schemas
from ai.data_generator import generate_customer
from mobile.conftest import customer_env
from utils.helpers import generate_ktp_number


def test_ktp_number_should_be_sixteen_digits_and_differ_between_calls():
    first, second = generate_ktp_number(), generate_ktp_number()
    assert re.fullmatch(r"\d{16}", first) and first.startswith("3171")
    assert first != second


def test_customer_env_should_cover_every_variable_the_flows_use():
    env = customer_env(generate_customer(complete=None, seed=1).data)
    expected = {"OUTLET_NAME", "PHONE", "EMAIL", "CONTACT_PERSON", "STREET_ADDRESS", "CHANNEL", "CUSTOMER_TYPE",
                "ADDRESS_TYPE", "PROVINCE", "CITY", "DISTRICT", "SUB_DISTRICT", "POSTAL_CODE", "KTP"}
    assert expected <= set(env)
    assert all(isinstance(value, str) and value for value in env.values())


def test_the_channel_should_be_regex_escaped_because_maestro_reads_selector_text_as_a_regex():
    env = customer_env(generate_customer(complete=None, seed=1).data)
    assert re.fullmatch(env["CHANNEL"], schemas.CUSTOMER_OPTIONS["channel"])
    assert "(" not in env["CHANNEL"].replace("\\(", "")


def test_the_location_should_come_from_the_verified_catalog_not_from_a_model():
    env = customer_env(generate_customer(complete=None, seed=1).data)
    location = schemas.LOCATIONS[0]
    assert (env["PROVINCE"], env["CITY"], env["POSTAL_CODE"]) == (
        location["province"], location["city"], location["postal_code"])


def test_the_outlet_name_should_be_unique_per_customer():
    names = {generate_customer(complete=None).data["outlet_name"] for _ in range(5)}
    assert len(names) == 5
