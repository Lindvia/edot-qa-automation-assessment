"""Step 4 helper: ask a model whether the expected value in the failing assertion matches the
manual test case. It only ever returns True / False / None - it cannot change a verdict on its
own, edit a test, or touch an assertion. Output is schema-validated; anything else is None."""

from typing import Callable, Optional

import jsonschema

from ai.data_generator import parse_json_object
from ai.triage.evidence import Failure
from ai.triage.rules import assertion_excerpt

Completer = Callable[[str, str], str]

SYSTEM_PROMPT = (
    "You are a QA triage assistant. You compare what a failing automated assertion expected with "
    "the manual test case. Reply with exactly one JSON object and nothing else."
)

USER_PROMPT = (
    "Test case {case_id} - {title}\n"
    "Expected result (from the test case): {expected}\n"
    "Test data: {data}\n\n"
    "Failing assertion output:\n{excerpt}\n\n"
    "Does the value the assertion EXPECTED agree with the test case's expected result? "
    'Reply {{"expected_value_correct": true|false|null, "reason": "<= 25 words"}}. '
    "Use null if you cannot tell. Do not judge whether the product is right."
)

ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["expected_value_correct", "reason"],
    "properties": {
        "expected_value_correct": {"type": ["boolean", "null"]},
        "reason": {"type": "string", "maxLength": 300},
    },
}

MAX_FIELD = 400  # characters of the sheet text sent to the model (token cost)


def make_judge(complete: Optional[Completer]):
    """Return a judge(failure, case) -> bool|None, or None when no model is available."""
    if complete is None:
        return None

    def judge(failure: Failure, case: Optional[dict]) -> Optional[bool]:
        if case is None:
            return None
        prompt = USER_PROMPT.format(
            case_id=case["id"],
            title=str(case.get("title", ""))[:120],
            expected=str(case.get("expected", ""))[:MAX_FIELD],
            data=str(case.get("data", ""))[:200],
            excerpt=assertion_excerpt(failure.message),
        )
        try:
            answer = parse_json_object(complete(SYSTEM_PROMPT, prompt))
            jsonschema.validate(answer, ANSWER_SCHEMA)
        except Exception:  # noqa: BLE001 - provider down or invalid answer: no opinion, never a verdict
            return None
        failure_reason = answer["reason"]
        judge.last_reason = failure_reason  # exposed for the report
        return answer["expected_value_correct"]

    judge.last_reason = ""
    return judge
