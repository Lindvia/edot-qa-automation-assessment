"""The five-step evidence walk. Stops at the FIRST step that explains the failure.

 1. Exception (element not found, timeout) or failed assertion?   exception -> script / environment
 2. Did the locator resolve to the intended, unique element?       no        -> script / environment
 3. Did every earlier step succeed, were preconditions met?        no        -> script / environment
 4. Was the expected value itself correct per the test case?       no        -> script / environment
 5. Does it reproduce consistently or only sometimes?              sometimes -> flaky
    Consistent and nothing above matched                                     -> product bug

The verdict is a PROPOSAL for a human. Steps 1-3 and 5 are plain rules (no tokens spent).
Only step 4 may ask a model, and only for failures that survived steps 1-3.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ai.triage.evidence import Failure

SCRIPT_OR_ENV = "script/environment defect"
PRODUCT_BUG = "product bug"
FLAKY = "flaky"

# judge(failure, case) -> True (expected value is right) / False (wrong) / None (cannot tell)
Judge = Callable[[Failure, Optional[dict]], Optional[bool]]
# rerun(failure) -> ["passed" | "failed", ...] from extra executions of the same test
Rerun = Callable[[Failure], List[str]]


@dataclass
class StepResult:
    number: int
    question: str
    answer: str  # "yes" | "no" | "unknown"
    detail: str
    decisive: bool = False


@dataclass
class Verdict:
    verdict: str
    matched_step: int
    confidence: str  # high / medium / low
    steps: List[StepResult] = field(default_factory=list)
    used_ai: bool = False
    summary: str = ""


def exception_type(message: str) -> str:
    """'playwright._impl._errors.TimeoutError: ...' -> 'TimeoutError'."""
    match = re.match(r"\s*([\w.]+)\s*:", message or "")
    return match.group(1).split(".")[-1] if match else "Unknown"


def first_lines(text: str, count: int = 8, width: int = 220) -> str:
    return "\n".join(line[:width] for line in (text or "").splitlines()[:count])


def assertion_excerpt(message: str, limit: int = 600) -> str:
    """The few lines that say what was expected and what was seen (kept short: token cost)."""
    keep = [
        line.strip()
        for line in (message or "").splitlines()
        if re.search(r"Expect|Actual value|unexpected value|expected|Error:|waiting for", line, re.I)
    ]
    return "\n".join(keep)[:limit]


def _step1(f: Failure) -> StepResult:
    kind = exception_type(f.message)
    question = "Exception (element not found, timeout) or failed assertion?"
    if kind == "AssertionError":
        return StepResult(1, question, "no", "A failed assertion (AssertionError), not an exception.")
    if kind == "Failed" and "Precondition" in f.message:
        return StepResult(1, question, "no", "A precondition check failed (handled in step 3).")
    environment = bool(re.search(r"net::ERR|ECONNREFUSED|Target (page|closed)|ERR_|503|502|CERT", f.message))
    note = " Looks like an environment / network problem." if environment else ""
    return StepResult(1, question, "yes", f"{kind}: an exception, almost always script or environment.{note}", True)


def _step2(f: Failure) -> StepResult:
    question = "Did the locator resolve to the intended, unique element?"
    message = f.message
    if "strict mode violation" in message:
        return StepResult(2, question, "no", "Strict-mode violation: the locator matched more than one element.", True)
    many = re.search(r"locator resolved to (\d+) elements", message)
    if many and int(many.group(1)) > 1:
        return StepResult(2, question, "no", f"The locator resolved to {many.group(1)} elements, not one.", True)
    maestro_not_found = re.search(r"Element not found|Unable to find element|No visible element", message)
    if re.search(r"element\(s\) not found", message) or maestro_not_found or (
        "Actual value: None" in message and "waiting for" in message
    ):
        return StepResult(
            2, question, "no",
            "The locator found no element (page changed or locator wrong), so the assertion never saw the target.",
            True,
        )
    if re.search(r"resolved to <", message):
        return StepResult(2, question, "yes", "The locator resolved to a single element.")
    return StepResult(2, question, "unknown", "No locator evidence in the error (plain assert).")


def _step3(f: Failure) -> StepResult:
    question = "Did every earlier step succeed and were the preconditions met?"
    if f.status == "broken":
        return StepResult(3, question, "no", "The test is 'broken' (setup/teardown/fixture error), not a clean failure.", True)
    if "Precondition failed" in f.message:
        return StepResult(3, question, "no", "A precondition from an earlier test or fixture was not met.", True)
    top_level_failed = [name for depth, name, status in f.steps if depth == 0 and status in ("failed", "broken")]
    if len(top_level_failed) > 1:
        return StepResult(3, question, "no", f"Several steps failed before the assertion: {top_level_failed[:3]}", True)
    ok = sum(1 for depth, _, status in f.steps if depth == 0 and status == "passed")
    return StepResult(3, question, "yes", f"{ok} earlier top-level step(s) passed; preconditions look met.")


def _step4(f: Failure, case: Optional[dict], judge: Optional[Judge]) -> (StepResult, bool):
    question = "Was the expected value itself correct according to the test case?"
    if case is None:
        return StepResult(4, question, "unknown", "No matching test case found in the sheet (missing case_id label)."), False
    if judge is None:
        return StepResult(4, question, "unknown", f"Not checked ({case['id']}: AI judge not available)."), False
    correct = judge(f, case)
    if correct is False:
        return StepResult(4, question, "no", f"The model judged the asserted expectation to contradict {case['id']}.", True), True
    if correct is True:
        return StepResult(4, question, "yes", f"The model judged the expectation consistent with {case['id']}."), True
    return StepResult(4, question, "unknown", "The model could not tell (or its answer was invalid)."), True


def _step5(f: Failure, rerun: Optional[Rerun]) -> (StepResult, str):
    question = "Does it reproduce consistently, or only sometimes?"
    passed, failed = f.history["passed"], f.history["failed"]
    runs = f.reruns or (rerun(f) if rerun else [])
    f.reruns = runs
    if passed and failed:
        return StepResult(5, question, "no", f"History is mixed ({passed} pass / {failed} fail): intermittent.", True), "history"
    if runs and "passed" in runs:
        return StepResult(5, question, "no", f"A re-run passed ({runs}): intermittent.", True), "rerun"
    if runs:
        return StepResult(5, question, "yes", f"Failed again on {len(runs)} re-run(s).", False), "rerun"
    if failed > 1:
        return StepResult(5, question, "yes", f"Failed in all {failed} recorded runs.", False), "history"
    return StepResult(5, question, "unknown", "Only one observation; re-run it to confirm.", False), "single"


def classify(f: Failure, case: Optional[dict] = None, judge: Optional[Judge] = None,
             rerun: Optional[Rerun] = None) -> Verdict:
    """Walk the five steps in order and stop at the first that explains the failure."""
    steps: List[StepResult] = []

    for step in (_step1(f), _step2(f), _step3(f)):
        steps.append(step)
        if step.decisive:
            confidence = "high" if step.number != 2 else "medium"
            return Verdict(SCRIPT_OR_ENV, step.number, confidence, steps, False, step.detail)

    step4, used_ai = _step4(f, case, judge)
    steps.append(step4)
    if step4.decisive:
        return Verdict(SCRIPT_OR_ENV, 4, "medium", steps, used_ai, step4.detail)

    step5, basis = _step5(f, rerun)
    steps.append(step5)
    if step5.decisive:
        return Verdict(FLAKY, 5, "medium", steps, used_ai, step5.detail)

    confident = step4.answer == "yes" and step5.answer == "yes"
    confidence = "medium" if confident else "low"
    summary = "Passed every check and reproduces; most likely a product bug."
    if not confident:
        summary = "No script or environment cause found, but the expected value or the reproduction is unverified."
    return Verdict(PRODUCT_BUG, 5, confidence, steps, used_ai, summary)
