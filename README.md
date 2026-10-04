# eDOT QA Automation take-home

Python + Pytest + Playwright (web), Allure reporting, and AI inside the suite (test data and failure
triage). Target: eSuite (`https://esuite.edot.id`). See [AI_USAGE.md](AI_USAGE.md) for how AI is used
and `docs/edot-test-cases.xlsx` for the manual test cases (Phase 1).

> **Status.** Web suite, AI test-data module, AI failure triage and the test-case sheet are done.
> The **mobile (Maestro) suite runs on a real phone**: MOB-01, 02, 03 and 05 pass; **MOB-04 currently fails** on a value the phone's
> keyboard changed while typing (open item, not weakened): see [Mobile](#mobile-maestro--pytest).
> The evidence (full web Allure report, triage report with the AI judge) is in [`evidence/`](#evidence-in-this-repo-evidence).

## Contents

- [Requirements](#requirements) · [Setup](#setup) · [Configuration](#configuration)
- [Run the web suite](#run-the-web-suite) · [Unit tests](#unit-tests-offline)
- [Allure report](#allure-report)
- [AI failure triage](#ai-failure-triage) · [Triage evidence](#triage-evidence)
- [Mobile](#mobile-maestro--pytest)
- [Project layout](#project-layout) · [Engineering rules](#engineering-rules) · [Known behaviour of the environment](#known-behaviour-of-the-environment)

## Requirements

- Python 3.10+ (developed on 3.14)
- Chromium, installed by Playwright (below)
- [Allure Commandline](https://allurereport.org/docs/install/) to render the HTML report
  (not needed to run the tests; `allure-pytest` writes the raw results)
- For the mobile suite: Java 17+, Maestro CLI, `adb`, an emulator or device (see [docs/MOBILE_SETUP.md](docs/MOBILE_SETUP.md))

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env              # then fill in the values (see below)
```

## Configuration

Everything comes from environment variables, loaded from `.env` (gitignored). **No credentials or
API keys are stored in the repository.**

| Variable | Used for |
|---|---|
| `ESUITE_URL` | eSuite base URL (default `https://esuite.edot.id`) |
| `ESUITE_EMAIL`, `ESUITE_PASSWORD` | web login (supplied with the assignment; put them in `.env`) |
| `HEADLESS` | `true` (default) or `false` to watch the browser |
| `DELETE_WAIT_SECONDS` | how long a deleted company may stay in the list (default 180) |
| `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY` | optional free AI: any OpenAI-compatible endpoint (Groq, Gemini, OpenRouter, a local Ollama). `AI_API_KEY` is not needed for Ollama. Examples are in `.env.example` |
| `ANTHROPIC_API_KEY` | optional alternative, used only when `AI_BASE_URL` is empty |
| none of the above | test data falls back to Faker and triage runs rules-only |
| `FAKER_SEED` | seed of the offline fallback |
| `MOBILE_APP_ID`, `MOBILE_COMPANY_ID`, `MOBILE_USERNAME`, `MOBILE_PASSWORD` | mobile login (password never in a YAML file) |
| `MAESTRO_CMD`, `MOBILE_RECORD`, `MOBILE_FLOW_TIMEOUT` | how to call Maestro (on Windows the full path to `maestro.bat`), optional screen recording, per-flow timeout |

## Run the web suite

```bash
python -m pytest -m smoke                       # login reaches the dashboard
python -m pytest -m negative                    # login + wizard negatives
python -m pytest web/tests/test_companies.py    # companies page, wizard, address cascade
python -m pytest web/tests/test_company_lifecycle.py   # create > verify > delete one company
python -m pytest web/tests                      # everything (creates and deletes one company)
```

The session logs in **once** through the UI and shares the session through `storage_state`
(`auth/`, gitignored). Negative login tests use a fresh context on purpose.

`test_company_lifecycle.py` creates one company and deletes it again. If a step fails halfway, the
module teardown still deletes it, so the shared environment is left as it was.

## Unit tests (offline)

No browser, network or API key needed:

```bash
python -m pytest tests/unit
```

They cover the AI data module (schema validation, retry, Faker fallback) and the triage rules.

## Allure report

`allure-pytest` writes raw results to `allure-results/` on every run. A screenshot is attached to
every failed web test, the generated test data is attached to the tests that use it, and the measured
delete delay is attached to the delete test.

```bash
python -m pytest web/tests --clean-alluredir      # start a fresh results folder
allure generate allure-results -o allure-report --clean
allure open allure-report
```

(`--clean-alluredir` is deliberately not a default: it would erase results on any run, including
`--collect-only`.)

## AI failure triage

Runs **after** the suite, reads the Allure results and writes a Markdown report with a **proposed**
verdict per failure: *script/environment defect*, *product bug* or *flaky*, with the evidence walked
in this order, stopping at the first match:

1. Exception (timeout, element not found) or failed assertion?
2. Did the locator resolve to the intended, unique element?
3. Did every earlier step succeed and were the preconditions met?
4. Was the expected value itself correct according to the test case? (the only step that may call a model)
5. Does it reproduce consistently, or only sometimes? (mixed history or a passing re-run = flaky)

```bash
python -m ai.triage                       # allure-results -> triage-report.md
python -m ai.triage --rerun 2             # re-run candidate product bugs to test for flakiness
python -m ai.triage --no-ai               # rules only
```

It never edits a test, never changes an assertion and never files or closes a bug. Details, prompts
and failure modes: [AI_USAGE.md](AI_USAGE.md).

## Triage evidence

Deliberately failing tests live in `web/tests/test_triage_demo.py` (excluded from normal runs): a
locator pointing at the wrong element, a click on a control that does not exist, and a wrong expected
value. They are real failures: nothing is skipped or weakened.

```bash
python -m pytest web/tests/test_triage_demo.py -m demo --alluredir allure-results-demo --clean-alluredir
python -m ai.triage --results allure-results-demo --out evidence/triage-report-demo.md
allure generate allure-results-demo -o evidence/allure-demo-report --clean
```

(The results go to `allure-results-demo`, not under `test-results/`: pytest-playwright wipes that folder
at the start of every run.)

### Evidence in this repo (`evidence/`)

| File | What it is |
|---|---|
| `allure-web-report/` | Full Allure report of the web suite: 13 of 13 passed on 4 Oct 2026. Open `index.html` through a local server (`allure open evidence/allure-web-report`). The generated company data is attached to the tests that use it (source `ai`: generated by Gemini in this run). |
| `triage-report-demo.md` | Triage of the three deliberate failures with the Gemini judge on: 1 and 2 decided by rules (steps 2 and 1), 3 decided at step 4 by the model, which noted the test case expects "Welcome Back," but the assertion checks "Selamat Datang,". All three are proposed as script defects; nothing was edited or filed. |
| `allure-demo-report/` | Allure report of the same three failures, with the failure screenshots attached. |

There is no mobile Allure report in this folder: the mobile tests were run on a phone in separate
sessions (see [Mobile](#mobile-maestro--pytest) for the exact state of each test).

One intermittent failure was seen once and has not been explained: in the first full web run the
Register Company form had every field filled except Company Name, so Next stayed disabled (WEB-08,
and WEB-09/WEB-12 failed on their precondition). The same module passed on the next run and the full
suite passed after that. It was not fixed because the cause is unknown; it is documented here instead.

## Mobile (Maestro + Pytest)

**State on a real phone (Realme, Android 16, fallback company 5049209), 4 Oct 2026:** MOB-01 and MOB-02
passed earlier that day; in the last customer run MOB-03 and MOB-05 passed and **MOB-04 failed**. The
customer tests take about 10 minutes (the new customer sits at the end of a ~300 card list).

**Open item, MOB-04.** MOB-04 first passed with loose "below/above the name" checks, which a
neighbouring card can satisfy (a wrong status passed that way). It now selects the card itself and
requires each field inside it; a wrong status fails even with similar cards on screen (checked on the
phone). With the stronger check it failed: the card showed "Jl. Gator Subroto No. 45" for the entered
"Jl. Gatot Subroto No. 45". The cause is **not confirmed**; the likely one is the phone keyboard's
autocorrect changing a word while it was typed (earlier streets passed because autocorrect left them
alone). The assertion was kept strict on purpose. Planned next: check the typed value right after
typing, so such a failure is labelled as a typing problem, and turn off autocorrect on the test phone.

| Part | State |
|---|---|
| Pytest wrapper (`mobile/maestro_runner.py`, `mobile/conftest.py`): runs a flow, passes credentials as `-e` env vars, masks secrets, attaches Maestro output / debug screenshots / optional screen recording to Allure | done, tested with a fake `maestro` |
| Shared login sub-flow `flows/shared/login.yaml` (ids read from the real screen), used with `runFlow` by every flow | done, run on a phone |
| `login_success.yaml` (MOB-01), `login_wrong_password.yaml` (MOB-02: "Oops" / "Wrong login combination" / "OK") | both **pass** on a phone. Google Password Manager's "Use your saved password" sheet covers the form on launch; the shared login dismisses it ("Later") and clears each field before typing |
| `create_customer.yaml` (MOB-03, Tier 2): Basic, Locations (province > postal cascade), Documents (KTP + in-app camera photo), approval signature, confirmation, then the customer is found in the list | **passes** |
| `verify_customer_card.yaml` (MOB-04, Tier 2): the card shows the entered name, address, customer type, "Waiting for Approval" and a customer number (one assertion per field, each tied to that card) | **fails** in the last run, see the open item above |
| `create_customer_without_name.yaml` (MOB-05, Negative): Continue is disabled without an outlet name and enabled once one is typed | **passes** |

Things the app does that shape the tests (all found on a device):

- **No customer detail screen.** Cards in the New Customer List are not tappable, so MOB-04 reads the
  card instead of a detail page. Phone, email, contact person, channel and the location cascade are
  not shown anywhere after saving, so they cannot be asserted.
- **The app is always left logged out.** A session-wide fixture (`logged_out_at_the_end` in
  `mobile/conftest.py`) clears eWork's data with `adb shell pm clear` when the mobile session ends,
  even after failures, so the phone never stays on a logged-in dashboard. If adb is missing or the
  phone does not answer, the run warns instead of failing. (It is per session, not per test, because
  of the next point.)
- **Saved on the device first** ("will be uploaded when an internet connection is available"). The
  verify flow therefore never clears the app data, and MOB-05 (which logs in again) runs last.
- **The list has no search** and shows the oldest customer first, so the finder flow swipes to the
  end and then scrolls to the name.
- **Customers cannot be deleted** from the app, so every run that reaches "Data Saved" leaves one
  `... QA<LETTERS>` customer in the shared company 5049209. **Test data left behind by the development
  runs: at least CUST-00287 (a manual probe, "Toko QA Probe"), CUST-00289, CUST-00290 and CUST-00291**
  (CUST-00288 is unconfirmed). They need to be removed by someone with access to the customer
  management side of eSuite. The web suite leaves nothing behind: it deletes its company even when a
  test fails.
- **Maestro quirks:** `hideKeyboard` presses Back when no keyboard is open (it left the form once), and
  selector text is a regex, so the channel name `General Trade (GT)` is escaped by the wrapper.
- Free-text data comes from the AI data module (Faker fallback). The dropdown options and the location
  are a verified catalog (`CUSTOMER_OPTIONS`, `LOCATIONS`), because a model cannot know them.

Detailed step-by-step (install, device, package id, inspection, first run): [docs/MOBILE_SETUP.md](docs/MOBILE_SETUP.md).

### Prerequisites to run it

1. Java 17+ and the Maestro CLI. It runs natively on Windows (unzip, add `bin` to PATH, set
   `MAESTRO_CMD` to the full path of `maestro.bat`); macOS/Linux use `maestro`. `maestro --version`
   must work.
2. A device or emulator visible to `adb devices` (USB debugging on). On Realme/Oppo phones see the
   install-prompt note in [docs/MOBILE_SETUP.md](docs/MOBILE_SETUP.md): the runner already passes
   `--no-reinstall-driver`, so Maestro's two helper apps are installed once by hand.
3. The eWork SFA package id: `id.edot.ework` (`adb shell pm list packages | grep -i ework`).
4. In `.env`: `MOBILE_APP_ID`, `MOBILE_COMPANY_ID`, `MOBILE_USERNAME`, `MOBILE_PASSWORD`, `MAESTRO_CMD`.
   Optional: `MOBILE_RECORD=true` (needs `adb` on PATH), `MOBILE_FLOW_TIMEOUT` (default 900 s).

```bash
python -m pytest mobile/tests -m mobile         # runs into the same allure-results as the web suite
python -m pytest web/tests mobile/tests         # web + mobile in one Allure run
```

### Credentials note

Creating a user for a company created by the web suite returned HTTP 500 `"error in account center"`
even with unique values, so the mobile suite runs against the brief's **fallback company 5049209**
(user `salesmanqaauto`, password in `.env`), not the company created in the web suite. The brief says
the fallback "may be expired"; on 2 and 4 Oct 2026 it was still accepted (see the state above for each test).

## Project layout

```
config/settings.py            environment variables only
ai/data_generator.py          AI test data: schema validation, retry, Faker fallback
ai/schemas.py                 JSON schemas + verified dropdown / location catalogs
ai/triage/                    failure triage (evidence, rules, judge, report, cli)
mobile/maestro_runner.py      runs Maestro flows from Pytest, attaches output to Allure
mobile/flows/                 Maestro YAML (shared/ sub-flows: login, open_registration, fill_basic, find_customer_card)
mobile/tests/                 Pytest wrappers around the flows
web/pages/                    page objects (all locators live here), registered as fixtures
web/conftest.py               login once (storage_state), failure screenshot, company_data fixture
web/tests/                    specs; test_triage_demo.py holds the deliberate failures
tests/unit/                   offline tests: AI modules, triage, Maestro wrapper and flow files
utils/helpers.py              pure helpers (unique names)
docs/edot-test-cases.xlsx     Phase 1 manual test cases
```

## Engineering rules

- **Page Object Model on fixtures.** Specs never construct a page object or contain a raw selector;
  they ask for `dashboard_page`, `companies_page`, ... Each page object keeps its locators in one
  object, has `is_ready()`, and keeps assertions in `validate_*` methods.
- **Locator priority:** `data-testid` > role + accessible name > stable attribute (`name` / `id` /
  `aria-*`) > text, with a comment justifying text. eSuite exposes no `data-testid`, so role,
  placeholder and text are what is left; every text locator carries a comment.
- **No `sleep()`.** Only Playwright auto-waiting and `expect()`. Reload loops (list refresh) are
  bounded by a time budget and re-raise the assertion if the condition never holds.
- **Tier 2 assertions** (create / edit / delete) assert the data itself, not a toast, and are marked
  with a `# Tier 2` comment so a reviewer can tell a product bug from a script defect.
- **No weakened assertions.** A failing test stays failing; expected values are never changed to match
  the actual result.
- **Shared environment hygiene.** Created data has a unique `QA<LETTERS>` suffix and is deleted at the
  end, even when a test fails.

## Known behaviour of the environment

Found while building the suite; useful when reading a result:

- **Deleted companies stay in the list for a while.** The delete shows a success toast at once, but
  the company was still listed about 31 seconds later in a measured run. The delete test reloads the
  list until `DELETE_WAIT_SECONDS` runs out and attaches the measured delay.
- **A new company's detail page can stay blank for a moment.** The test reloads it a few times before
  asserting the data.
- **The UI differs between app versions** (for example the Companies header, and the optional branch
  step of the registration wizard). The tests assert only what the test cases promise.
- **Logins:** a wrong password shows "Incorrect password" followed by a per-request reference code
  (only the prefix is asserted); an unknown email and an unknown username show different dialogs.
