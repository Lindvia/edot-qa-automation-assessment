"""Offline tests for the Maestro wrapper and the flow files. A fake `maestro` stands in for the
real CLI, so no device, emulator, WSL or Java is needed."""

import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from config import settings
from mobile import maestro_runner as mr
from ai.triage.rules import SCRIPT_OR_ENV, classify
from tests.unit.test_triage import failure  # noqa: F401  (shared helper)

FLOWS = mr.FLOWS_DIR


@pytest.fixture
def fake_maestro(tmp_path):
    """A stand-in for the maestro CLI that records its argv and exits with the code in FAKE_EXIT."""
    script = tmp_path / "fake_maestro.py"
    record = tmp_path / "argv.json"
    script.write_text(textwrap.dedent(f"""
        import json, os, sys, time
        json.dump(sys.argv[1:], open(r"{record}", "w"))
        if os.environ.get("FAKE_SLEEP"): time.sleep(float(os.environ["FAKE_SLEEP"]))
        print("fake maestro ran")
        if os.environ.get("FAKE_EXIT", "0") != "0":
            print("Element not found: Text matching regex: Sign In", file=sys.stderr)
        sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
    """), encoding="utf-8")
    return [sys.executable, str(script)], record


ENV = {"APP_ID": "com.example.ework", "COMPANY_ID": "123", "USERNAME": "qa.user", "PASSWORD": "s3cret-value"}


# --------------------------------------------------------------------------- the wrapper
def test_command_should_pass_every_value_as_an_environment_flag_and_end_with_the_flow():
    command = mr.build_command("maestro", FLOWS / "login_success.yaml", ENV, Path("dbg"))
    assert command[:2] == ["maestro", "test"]
    assert command[-1].endswith("login_success.yaml")
    assert command.count("-e") == len(ENV)
    assert "PASSWORD=s3cret-value" in command


def test_wsl_prefix_should_be_split_into_separate_arguments():
    assert mr.build_command("wsl maestro", FLOWS / "login_success.yaml", {}, Path("d"))[:3] == ["wsl", "maestro", "test"]


def test_secrets_should_be_masked_in_the_printed_command():
    command = mr.build_command("maestro", FLOWS / "login_success.yaml", ENV, Path("dbg"))
    shown = mr.mask(command)
    assert "s3cret-value" not in shown and "PASSWORD=***" in shown
    assert "COMPANY_ID=123" in shown  # non-secret values stay readable


def test_a_passing_flow_should_report_success_and_never_leak_the_password(fake_maestro):
    cmd, record = fake_maestro
    result = mr.run_flow("login_success.yaml", ENV, cmd, timeout=60)
    assert result.passed and "fake maestro ran" in result.stdout
    assert "maestro-output" in result.attachments
    assert "s3cret-value" not in result.command and "s3cret-value" not in result.output
    received = json.loads(record.read_text())
    assert "PASSWORD=s3cret-value" in received  # the real CLI does get the real value
    assert received[0] == "test" and received[-1].endswith("login_success.yaml")


def test_a_failing_flow_should_report_failure_with_maestros_own_output(fake_maestro, monkeypatch):
    cmd, _ = fake_maestro
    monkeypatch.setenv("FAKE_EXIT", "1")
    result = mr.run_flow("login_success.yaml", ENV, cmd, timeout=60)
    assert not result.passed and result.returncode == 1
    assert "Element not found" in result.output


def test_a_flow_that_hangs_should_time_out_with_exit_code_124(fake_maestro, monkeypatch):
    cmd, _ = fake_maestro
    monkeypatch.setenv("FAKE_SLEEP", "5")
    result = mr.run_flow("login_success.yaml", ENV, cmd, timeout=1)
    assert result.returncode == 124 and "Timed out" in result.stderr


def test_an_unknown_flow_should_raise_instead_of_passing(fake_maestro):
    cmd, _ = fake_maestro
    with pytest.raises(FileNotFoundError):
        mr.run_flow("does_not_exist.yaml", ENV, cmd)


def test_clearing_the_app_session_should_run_pm_clear_for_the_app(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="Success\n", stderr="")

    monkeypatch.setattr(mr.shutil, "which", lambda name: "adb")
    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    assert mr.clear_app_session("id.edot.ework") is True
    assert calls == [["adb", "shell", "pm", "clear", "id.edot.ework"]]


@pytest.mark.parametrize("outcome", ["no_adb", "failure_output", "phone_does_not_answer"])
def test_clearing_the_app_session_should_report_false_when_it_could_not_log_out(monkeypatch, outcome):
    def fake_run(command, **kwargs):
        if outcome == "phone_does_not_answer":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 1, stdout="Failure [DELETE_FAILED_INTERNAL_ERROR]", stderr="")

    monkeypatch.setattr(mr.shutil, "which", lambda name: None if outcome == "no_adb" else "adb")
    monkeypatch.setattr(mr.subprocess, "run", fake_run)
    assert mr.clear_app_session("id.edot.ework") is False


def test_recording_should_stay_off_without_adb_or_when_disabled():
    assert mr.ScreenRecorder(False).enabled is False
    assert mr.ScreenRecorder(True).enabled == (mr.shutil.which("adb") is not None)


# ------------------------------------------------------------------------- the flow files
def load_flow(path: Path):
    config, *steps = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    return config, (steps[0] if steps else [])


ALL_FLOWS = sorted(FLOWS.rglob("*.yaml"))


def test_there_should_be_flows_to_check():
    names = {p.name for p in ALL_FLOWS}
    assert {"login.yaml", "login_success.yaml", "login_wrong_password.yaml"} <= names


@pytest.mark.parametrize("path", ALL_FLOWS, ids=lambda p: p.name)
def test_every_flow_should_be_valid_yaml_with_an_app_id_from_the_environment(path):
    config, steps = load_flow(path)
    assert config["appId"] == "${APP_ID}"
    assert isinstance(steps, list) and steps


@pytest.mark.parametrize("path", ALL_FLOWS, ids=lambda p: p.name)
def test_no_flow_should_hardcode_credentials_or_test_data(path):
    text = path.read_text(encoding="utf-8")
    passwords = [value for value in (settings.MOBILE_PASSWORD, settings.ESUITE_PASSWORD) if value]  # from .env, never in the repo
    for forbidden in ("5049209", "salesmanqaauto", "Wrong#Pass", *passwords):
        assert forbidden not in text, f"{forbidden} must come from an environment variable, not the YAML"
    _, steps = load_flow(path)
    for step in steps:
        if isinstance(step, dict) and "inputText" in step:
            assert str(step["inputText"]).startswith("${"), f"literal inputText in {path.name}: {step}"


@pytest.mark.parametrize("path", ALL_FLOWS, ids=lambda p: p.name)
def test_no_flow_should_use_coordinate_taps_or_fixed_waits(path):
    text = path.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
    assert not re.search(r"\bpoint\s*:", code), "coordinate taps are a last resort and need a justification"
    assert "sleep" not in code, "no sleep-based waiting: use Maestro's own wait commands"


def test_login_flows_should_reuse_the_shared_login_sub_flow():
    for name in ("login_success.yaml", "login_wrong_password.yaml"):
        _, steps = load_flow(FLOWS / name)
        assert {"runFlow": "shared/login.yaml"} in steps


def test_the_wrong_password_flow_should_assert_the_specific_error_message():
    _, steps = load_flow(FLOWS / "login_wrong_password.yaml")
    asserted = [s["assertVisible"] for s in steps if isinstance(s, dict) and "assertVisible" in s]
    assert "Wrong login combination" in asserted and "Oops" in asserted


def flow_commands(path: Path):
    """Every command of a flow, including those nested in repeat/runFlow blocks."""
    _, steps = load_flow(path)

    def walk(items):
        for item in items:
            yield item
            if isinstance(item, dict):
                for value in item.values():
                    if isinstance(value, dict) and isinstance(value.get("commands"), list):
                        yield from walk(value["commands"])

    return list(walk(steps))


@pytest.mark.parametrize("path", ALL_FLOWS, ids=lambda p: p.name)
def test_every_sub_flow_a_flow_runs_should_exist(path):
    for command in flow_commands(path):
        if isinstance(command, dict) and isinstance(command.get("runFlow"), str):
            target = path.parent / command["runFlow"]
            assert target.exists(), f"{path.name} runs {command['runFlow']}, which does not exist"


def test_the_customer_flows_should_be_present_and_use_only_variables_for_test_data():
    names = {p.name for p in ALL_FLOWS}
    assert {"create_customer.yaml", "verify_customer_card.yaml", "create_customer_without_name.yaml"} <= names
    text = "".join((FLOWS / name).read_text(encoding="utf-8")
                   for name in ("create_customer.yaml", "shared/fill_basic.yaml"))  # the flow and its Basic step
    for variable in ("OUTLET_NAME", "PHONE", "STREET_ADDRESS", "PROVINCE", "POSTAL_CODE", "KTP", "CHANNEL"):
        assert "${" + variable + "}" in text, f"{variable} must come from the wrapper"


def test_no_flow_should_press_hide_keyboard_right_after_a_dropdown_selection():
    """With no keyboard open Maestro's hideKeyboard presses Back and leaves the form (found on a device)."""
    for path in ALL_FLOWS:
        previous = None
        for command in flow_commands(path):
            if command == "hideKeyboard" and isinstance(previous, dict) and "tapOn" in previous:
                tapped = previous["tapOn"]
                assert not (isinstance(tapped, dict) and tapped.get("id") == "tvName"), (
                    f"hideKeyboard right after picking a dropdown option in {path.name}")
            previous = command


def test_the_card_assertions_should_be_tied_to_the_card_not_to_screen_position():
    """`below`/`above` are satisfied by a neighbouring card (a wrong status passed that way), so every field
    assertion must select the card by its name and require the field inside it."""
    text = (FLOWS / "verify_customer_card.yaml").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(below|above|leftOf|rightOf)\s*:", text, re.M)
    field_checks = [c["assertVisible"] for c in flow_commands(FLOWS / "verify_customer_card.yaml")
                    if isinstance(c, dict) and isinstance(c.get("assertVisible"), dict)
                    and "containsDescendants" in c["assertVisible"]]
    assert len(field_checks) == 4  # address, customer type, status, customer number
    for check in field_checks:
        assert check["containsChild"]["id"] == "tv_name" and check["containsChild"]["text"] == "${OUTLET_NAME}"


def test_the_verify_flow_should_not_clear_the_app_state():
    """A new customer is saved on the device first: clearing the state would delete it."""
    _, steps = load_flow(FLOWS / "verify_customer_card.yaml")
    launch = next(s for s in steps if isinstance(s, dict) and "launchApp" in s)
    assert launch["launchApp"]["clearState"] is False


# --------------------------------------------------------- triage understands Maestro failures
def test_triage_should_treat_a_maestro_element_not_found_as_a_locator_problem():
    message = ("AssertionError: Maestro flow login_success.yaml failed (exit 1):\n"
              "Element not found: Text matching regex: Sign In")
    verdict = classify(failure(message))
    assert (verdict.verdict, verdict.matched_step) == (SCRIPT_OR_ENV, 2)
