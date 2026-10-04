# CLAUDE.md

Behavioral rules for every session on this project (the first four are the general working rules, the
fifth is specific to this project). They bias toward caution over speed; for a trivial change, use
judgment.

## 1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State assumptions explicitly. If something is unclear, ask instead of guessing.
- If several interpretations exist, present them; don't pick one silently.
- If a simpler approach exists, say so. Push back when warranted.
- If you are confused, stop, name what is unclear, and ask.

## 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked, no abstractions for single-use code.
- No flexibility or configurability that was not requested.
- No error handling for scenarios that cannot happen.
- If it could be half the length, rewrite it.

## 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

- Do not "improve" adjacent code, comments or formatting; match the existing style.
- Do not refactor things that are not broken.
- Remove imports, variables and files that YOUR change made unused; mention, but do not delete,
  pre-existing dead code.
- Every changed line should trace directly to the request.

## 4. Goal-Driven Execution

Define success criteria. Loop until verified.

- Turn a task into a verifiable goal (a failing test that passes, a run that is green, a report that
  exists) before starting, and say what "done" means.
- For multi-step work, state a short plan with a check per step.
- Report results as they are: a failing test stays failing and is reported, never weakened.
- Never claim something works that was not run.

## 5. Clean Up Test Data

Every test that creates data on a shared environment removes it again, and the cleanup is verified.

- Cleanup runs even when the test fails (a fixture teardown / `finally`), not only on the happy path.
- Verify it: after a run, check that nothing is left (the record is gone from the list), not that a
  delete button was clicked.
- If the app offers no way to delete something, say so before creating it, create as little of it as
  possible, and list what was left behind in the README. Never run a data-creating test casually or "to
  see what happens": every run leaves something.
- Leave devices clean too: the phone is logged out when a mobile session ends.

## Project rules that already apply

The engineering rules in `README.md` ("Engineering rules": POM on fixtures, locator priority, no
sleeps, Tier 2 data assertions, no weakened assertions, cleanup of shared data) and
`AI_USAGE.md` (what AI may and may not do). Secrets live only in `.env` (gitignored); never type or
print a password.
