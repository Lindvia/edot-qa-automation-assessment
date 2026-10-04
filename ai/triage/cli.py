"""Run after the suite:  python -m ai.triage [--results allure-results] [--out triage-report.md]

  --no-ai      rules only (also what happens automatically when there is no API key)
  --rerun N    re-run each failure that reaches step 5 up to N times to see if it is intermittent
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from ai.data_generator import default_completer
from ai.triage.evidence import Failure, load_case, load_failures
from ai.triage.judge import make_judge
from ai.triage.report import build_report
from ai.triage.rules import classify


def rerun_test(failure: Failure, times: int) -> List[str]:
    """Run the same test again (its own pytest process, results kept out of the main folder)."""
    nodeid = failure.nodeid
    if not nodeid:
        return []
    outcomes = []
    for _ in range(times):
        with tempfile.TemporaryDirectory() as tmp:
            run = subprocess.run(
                [sys.executable, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider", f"--alluredir={tmp}"],
                capture_output=True, text=True, timeout=900,
            )
        outcomes.append("passed" if run.returncode == 0 else "failed")
        if outcomes[-1] == "passed":
            break  # one pass is enough to call it intermittent
    return outcomes


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ai.triage", description=__doc__)
    parser.add_argument("--results", default="allure-results")
    parser.add_argument("--sheet", default="docs/edot-test-cases.xlsx")
    parser.add_argument("--out", default="triage-report.md")
    parser.add_argument("--no-ai", action="store_true", help="rules only, never call a model")
    parser.add_argument("--rerun", type=int, default=0, metavar="N")
    args = parser.parse_args(argv)

    complete = None if args.no_ai else default_completer()
    judge = make_judge(complete)
    ai_mode = f"on ({complete.model})" if judge else "off (rules only)"

    rerun = (lambda failure: rerun_test(failure, args.rerun)) if args.rerun > 0 else None

    items = []
    for failure in load_failures(args.results):
        case = load_case(args.sheet, failure.case_id)
        if judge:
            judge.last_reason = ""
        verdict = classify(failure, case, judge, rerun)
        reason = judge.last_reason if judge and verdict.used_ai else ""
        items.append((failure, verdict, case, reason))

    Path(args.out).write_text(build_report(items, args.results, ai_mode), encoding="utf-8")
    print(f"Triage report written to {args.out} ({len(items)} failure(s)); AI judge: {ai_mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
