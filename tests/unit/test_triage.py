"""Offline tests for the failure triage: synthetic Allure results, no browser, no network."""

import json
import uuid

import pytest

from ai.triage import cli
from ai.triage.evidence import Failure, load_case, load_failures
from ai.triage.judge import make_judge
from ai.triage.report import build_report
from ai.triage.rules import FLAKY, PRODUCT_BUG, SCRIPT_OR_ENV, classify

# --- messages copied in shape from real failures seen in this project -------------------------
TIMEOUT = (
    "playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.\n"
    "Call log:\n  - waiting for get_by_role(\"button\", name=\"Register\")"
)
NOT_FOUND = (
    "AssertionError: Locator expected to be visible\nActual value: None\nError: element(s) not found\n"
    "Call log:\n  - Expect \"to_be_visible\" get_by_role(\"button\", name=\"Manage Company\") with timeout 5000ms\n"
    "  - waiting for get_by_role(\"button\", name=\"Manage Company\")"
)
STRICT = "Error: strict mode violation: get_by_text(\"Active\") resolved to 3 elements"
MANY = "AssertionError: Locator expected to have count '1'\nActual value: 3\nCall log:\n  - locator resolved to 3 elements"
PRECONDITION = "Failed: Precondition failed: the company was not created by the previous test"
VALUE_MISMATCH = (
    "AssertionError: Locator expected to be disabled\nActual value: enabled\nCall log:\n"
    "  - Expect \"to_be_disabled\" get_by_role(\"button\", name=\"Next\", exact=True) with timeout 5000ms\n"
    "  - waiting for get_by_role(\"button\", name=\"Next\", exact=True)\n"
    "    14 x locator resolved to <button>Next</button>\n       - unexpected value \"enabled\""
)

CASE = {"id": "WEB-10", "title": "Step 1 rejects a malformed email", "tier": "Negative",
        "data": "Email: nusantara.example.co.id",
        "expected": "The inline message \"Please provide a valid email address\" is shown under the Email field."}


def write_result(directory, name="Some test", status="failed", message=VALUE_MISMATCH, history_id="h1",
                 start=1000, case_id="WEB-10", steps=None, full_name="web.tests.test_x.TestX#test_y"):
    result = {
        "uuid": str(uuid.uuid4()), "name": name, "fullName": full_name, "historyId": history_id,
        "status": status, "start": start, "stop": start + 10,
        "statusDetails": {"message": message, "trace": "Traceback ..."},
        "labels": [{"name": "case_id", "value": case_id}] if case_id else [],
        "steps": steps if steps is not None else [{"name": "Open page", "status": "passed", "steps": []}],
        "attachments": [{"name": "failure-screenshot", "source": "shot.png", "type": "image/png"}],
    }
    path = directory / f"{result['uuid']}-result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    return result


def failure(message=VALUE_MISMATCH, status="failed", steps=None, history=None, reruns=None):
    return Failure("u", "A test", "web.tests.test_x.TestX#test_y", "WEB-10", "h", status, message, "",
                   steps if steps is not None else [(0, "Open page", "passed"), (0, "Check", "failed")],
                   [], 0, history or {"passed": 0, "failed": 1}, reruns or [])


class SpyJudge:
    def __init__(self, answer):
        self.answer, self.calls = answer, 0

    def __call__(self, f, case):
        self.calls += 1
        return self.answer


# ------------------------------------------------------------------------- steps 1 to 3
def test_an_exception_should_be_a_script_or_environment_defect_at_step_1():
    judge = SpyJudge(True)
    verdict = classify(failure(TIMEOUT), CASE, judge)
    assert (verdict.verdict, verdict.matched_step) == (SCRIPT_OR_ENV, 1)
    assert judge.calls == 0  # no tokens spent when rules already explain it


def test_a_missing_element_should_be_a_script_defect_at_step_2():
    verdict = classify(failure(NOT_FOUND), CASE, SpyJudge(True))
    assert (verdict.verdict, verdict.matched_step) == (SCRIPT_OR_ENV, 2)
    assert "no element" in verdict.steps[1].detail


@pytest.mark.parametrize("message", [STRICT, MANY])
def test_a_non_unique_locator_should_be_a_script_defect_at_step_2(message):
    verdict = classify(failure("AssertionError: " + message if "AssertionError" not in message else message), CASE)
    assert (verdict.verdict, verdict.matched_step) == (SCRIPT_OR_ENV, 2)


def test_a_failed_precondition_should_be_a_script_or_environment_defect_at_step_3():
    verdict = classify(failure(PRECONDITION), CASE, SpyJudge(True))
    assert (verdict.verdict, verdict.matched_step) == (SCRIPT_OR_ENV, 3)


def test_a_broken_test_should_be_decided_at_step_3():
    verdict = classify(failure(VALUE_MISMATCH, status="broken"), CASE)
    assert (verdict.verdict, verdict.matched_step) == (SCRIPT_OR_ENV, 3)


def test_several_failed_steps_before_the_assertion_should_be_decided_at_step_3():
    steps = [(0, "Login", "failed"), (0, "Open page", "failed")]
    assert classify(failure(VALUE_MISMATCH, steps=steps), CASE).matched_step == 3


# --------------------------------------------------------------------------- step 4
def test_an_expected_value_the_judge_calls_wrong_should_be_a_script_defect_at_step_4():
    verdict = classify(failure(), CASE, SpyJudge(False))
    assert (verdict.verdict, verdict.matched_step, verdict.used_ai) == (SCRIPT_OR_ENV, 4, True)


def test_without_a_judge_the_expected_value_should_stay_unverified_and_confidence_low():
    verdict = classify(failure(), CASE, None)
    assert verdict.verdict == PRODUCT_BUG
    assert verdict.confidence == "low"
    assert verdict.steps[3].answer == "unknown"


def test_a_failure_without_a_case_should_not_call_the_judge():
    judge = SpyJudge(False)
    verdict = classify(failure(), None, judge)
    assert judge.calls == 0 and verdict.verdict == PRODUCT_BUG


# --------------------------------------------------------------------------- step 5
def test_a_mixed_history_should_be_flaky():
    verdict = classify(failure(history={"passed": 2, "failed": 1}), CASE, SpyJudge(True))
    assert (verdict.verdict, verdict.matched_step) == (FLAKY, 5)


def test_a_rerun_that_passes_should_be_flaky():
    verdict = classify(failure(), CASE, SpyJudge(True), rerun=lambda f: ["failed", "passed"])
    assert verdict.verdict == FLAKY


def test_consistent_failures_with_a_confirmed_expected_value_should_be_a_product_bug():
    verdict = classify(failure(), CASE, SpyJudge(True), rerun=lambda f: ["failed", "failed"])
    assert (verdict.verdict, verdict.confidence) == (PRODUCT_BUG, "medium")


def test_a_single_unconfirmed_observation_should_be_a_low_confidence_product_bug():
    verdict = classify(failure(), CASE, SpyJudge(True))
    assert (verdict.verdict, verdict.confidence) == (PRODUCT_BUG, "low")
    assert "re-run" in verdict.steps[-1].detail


def test_the_walk_should_stop_at_the_first_decisive_step():
    assert [s.number for s in classify(failure(NOT_FOUND), CASE).steps] == [1, 2]


# ------------------------------------------------------------------------- the judge
def test_judge_should_return_the_models_boolean_when_the_answer_is_valid():
    judge = make_judge(lambda s, u: '{"expected_value_correct": false, "reason": "contradicts"}')
    assert judge(failure(), CASE) is False and judge.last_reason == "contradicts"


@pytest.mark.parametrize("answer", ["not json", '{"expected_value_correct": "yes", "reason": "x"}', '{"reason": "x"}'])
def test_judge_should_give_no_opinion_when_the_answer_is_invalid(answer):
    assert make_judge(lambda s, u: answer)(failure(), CASE) is None


def test_judge_should_give_no_opinion_when_the_provider_fails():
    def boom(system, user):
        raise ConnectionError("down")

    assert make_judge(boom)(failure(), CASE) is None


def test_no_completer_should_mean_no_judge():
    assert make_judge(None) is None


def test_judge_prompt_should_stay_small():
    seen = []
    judge = make_judge(lambda s, u: seen.append(u) or '{"expected_value_correct": null, "reason": "?"}')
    big_case = dict(CASE, expected="x" * 5000, data="y" * 5000)
    judge(failure("AssertionError: " + "z" * 5000), big_case)
    assert len(seen[0]) < 1800


# ------------------------------------------------------------------------ loading + report
def test_load_failures_should_keep_the_latest_result_per_test_with_its_history(tmp_path):
    write_result(tmp_path, status="passed", history_id="a", start=1)
    write_result(tmp_path, status="failed", history_id="a", start=2)   # latest = failed -> triaged
    write_result(tmp_path, status="failed", history_id="b", start=1)
    write_result(tmp_path, status="passed", history_id="b", start=2)   # latest = passed -> ignored
    found = load_failures(str(tmp_path))
    assert [f.history_id for f in found] == ["a"]
    assert found[0].history == {"passed": 1, "failed": 1}
    assert found[0].case_id == "WEB-10"


def test_nodeid_should_be_rebuilt_from_the_allure_full_name():
    f = failure()
    assert f.nodeid == "web/tests/test_x.py::TestX::test_y"


def test_load_case_should_read_the_expected_result_from_the_sheet():
    case = load_case("docs/edot-test-cases.xlsx", "WEB-08")
    assert case and case["tier"] == "Tier 2" and "Active" in case["expected"]
    assert load_case("docs/edot-test-cases.xlsx", "NOPE-1") is None


def test_report_should_state_that_verdicts_are_proposals_and_file_nothing():
    f = failure(NOT_FOUND)
    text = build_report([(f, classify(f, CASE), CASE, "")], "allure-results", "off (rules only)")
    assert "proposals for a human" in text
    assert "files nothing and closes nothing" in text or "Do NOT edit the assertion" in text
    assert "script/environment defect" in text and "Evidence walk" in text


def test_report_for_no_failures_should_say_so():
    assert "No failed or broken tests" in build_report([], "allure-results", "off")


def test_cli_should_write_a_report_without_an_api_key(tmp_path):
    write_result(tmp_path, message=NOT_FOUND)
    out = tmp_path / "report.md"
    assert cli.main(["--results", str(tmp_path), "--out", str(out), "--sheet", "docs/edot-test-cases.xlsx"]) == 0
    text = out.read_text(encoding="utf-8")
    assert "off (rules only)" in text and "script/environment defect" in text
