"""Write the triage report (Markdown). One section per failure with the evidence behind the verdict."""

from datetime import datetime
from typing import List, Optional, Tuple

from ai.triage.evidence import Failure
from ai.triage.rules import FLAKY, PRODUCT_BUG, SCRIPT_OR_ENV, Verdict, assertion_excerpt, first_lines

PROPOSED_ACTION = {
    SCRIPT_OR_ENV: "Fix or retry the script / environment. Check the locator, the data and the environment first. "
                   "Do NOT edit the assertion to make it pass.",
    PRODUCT_BUG: "Reproduce it by hand. If it reproduces and contradicts the test case, a person files the bug. "
                 "This tool files nothing and closes nothing.",
    FLAKY: "Investigate the timing / data dependency; keep the test failing in the report until it is stable. "
           "Do not add blanket retries or skips.",
}

ICON = {SCRIPT_OR_ENV: "SCRIPT/ENV", PRODUCT_BUG: "PRODUCT BUG", FLAKY: "FLAKY"}


def _table_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def build_report(items: List[Tuple[Failure, Verdict, Optional[dict], str]], results_dir: str, ai_mode: str) -> str:
    lines = [
        "# Failure triage report",
        "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M} from `{results_dir}`. AI step-4 judge: **{ai_mode}**.",
        "",
        "> **These verdicts are proposals for a human.** Nothing was filed, closed, edited or re-asserted. "
        "A failing test stays failing.",
        "",
    ]
    if not items:
        lines += ["No failed or broken tests found in the results.", ""]
        return "\n".join(lines)

    counts = {SCRIPT_OR_ENV: 0, PRODUCT_BUG: 0, FLAKY: 0}
    for _, verdict, _, _ in items:
        counts[verdict.verdict] += 1
    lines += [
        f"**{len(items)} failure(s):** {counts[SCRIPT_OR_ENV]} script/environment, "
        f"{counts[PRODUCT_BUG]} product bug, {counts[FLAKY]} flaky.",
        "",
        "| # | Test | Case | Proposed verdict | Decided at step | Confidence |",
        "|---|---|---|---|---|---|",
    ]
    for index, (failure, verdict, case, _) in enumerate(items, 1):
        lines.append(
            f"| {index} | {_table_cell(failure.name)} | {failure.case_id or '-'} | "
            f"**{verdict.verdict}** | {verdict.matched_step} | {verdict.confidence} |"
        )
    lines.append("")

    for index, (failure, verdict, case, judge_reason) in enumerate(items, 1):
        lines += [
            f"## {index}. {failure.name}",
            "",
            f"- **Proposed verdict: {ICON[verdict.verdict]} ({verdict.verdict})** - decided at step "
            f"{verdict.matched_step}, confidence {verdict.confidence}",
            f"- Case: {failure.case_id or 'not labelled'}"
            + (f" - {case['title']}" if case else ""),
            f"- Status: {failure.status}; history: {failure.history['passed']} pass / {failure.history['failed']} fail"
            + (f"; re-runs: {failure.reruns}" if failure.reruns else ""),
            f"- Summary: {verdict.summary}",
            "",
            "**Evidence walk (stops at the first match):**",
            "",
            "| Step | Question | Answer | Evidence |",
            "|---|---|---|---|",
        ]
        for step in verdict.steps:
            marker = " **<- decided**" if step.decisive else ""
            lines.append(f"| {step.number} | {step.question} | {step.answer}{marker} | {_table_cell(step.detail)} |")
        skipped = [n for n in range(1, 6) if n > verdict.matched_step]
        if skipped:
            lines.append(f"| {skipped[0]}-5 | (not needed) | - | The walk stopped at step {verdict.matched_step}. |")
        if judge_reason:
            lines += ["", f"AI step-4 note: _{judge_reason}_"]
        lines += [
            "",
            "**Error:**",
            "",
            "```",
            first_lines(failure.message, 8) or "(no message)",
            "```",
        ]
        excerpt = assertion_excerpt(failure.message)
        if excerpt and len(failure.message.splitlines()) > 8:  # the error above was cut short
            lines += ["", "**Assertion detail:**", "", "```", excerpt, "```"]
        shots = [a for a in failure.attachments if "screenshot" in a.lower()]
        if shots:
            lines += ["", f"Screenshot: `{shots[0].split(': ', 1)[-1]}`"]
        lines += ["", f"**Proposed action (human decision):** {PROPOSED_ACTION[verdict.verdict]}", ""]
    return "\n".join(lines)
