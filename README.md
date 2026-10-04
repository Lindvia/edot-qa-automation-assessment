# eDOT QA Automation take-home

Python + Pytest + Playwright (web), Allure reporting, and AI inside the suite (test data and failure
triage). Target: eSuite (`https://esuite.edot.id`). See [AI_USAGE.md](AI_USAGE.md) for how AI is used
and `docs/edot-test-cases.xlsx` for the manual test cases (Phase 1).

> **Status.** Web suite, AI test-data module, AI failure triage and the test-case sheet are done and
> verified (web: 13/13 passed). The **mobile (Maestro) suite runs on a real phone**: MOB-01, 02, 03 and 05
> passed; **MOB-04 is an open item** (a keyboard autocorrect changed the typed street). A fix is in the
> code but **not yet verified on a phone**, see [Limitations](#limitations).
> The evidence (full web Allure report, triage report with the AI judge) is in [`evidence/`](#evidence-in-this-repo-evidence).

## Contents

- [Limitations](#limitations)
- [Requirements](#requirements) · [Setup](#setup-step-by-step) · [Configuration](#configuration)
- [Run the web suite](#run-the-web-suite) · [Unit tests](#unit-tests-offline)
- [Allure report](#allure-report)
- [AI failure triage](#ai-failure-triage) · [Triage evidence](#triage-evidence)
- [Mobile](#mobile-maestro--pytest) · [CI](#ci-github-actions)
- [Project layout](#project-layout) · [Engineering rules](#engineering-rules) · [Known behaviour of the environment](#known-behaviour-of-the-environment)

## Limitations

Read these first; they are the honest gaps of this submission.

1. **MOB-04 (customer card shows the entered data) is not verified green.** On the last full run it
   failed because the phone keyboard autocorrected the typed street ("Gatot" became "Gator"). The cause
   is **confirmed** (the saved screen dump of the address field shows the changed text). The fix is in
   the repo but was **not run to completion on a phone**: (a) `create_customer.yaml` now asserts the
   address field right after typing, so such a failure is reported at the cause; (b) the AI prompt and the
   Faker fallback now use plain, well-known road names. The card assertion itself was **not weakened**.
2. **Mobile runs depend on the phone staying connected.** On the Realme test phone adb lost its USB
   debugging authorization or went offline every 10-15 minutes, so the last attempts could not
   finish. This is a device/USB problem, not a suite result. The runner now checks that the phone answers
   `adb shell echo ok` within 15 seconds before a session and stops with a clear message instead of
   hanging. The emulator could not be used (this PC has no hypervisor).
3. **Mobile test data cannot be cleaned.** The app has no delete for customers, so every run that saves
   a customer leaves one in the shared company 5049209 (list in the [Mobile](#mobile-maestro--pytest)
   section: CUST-00287, 00289, 00290, 00291, and 00288 unconfirmed). They need someone with eSuite
   customer-management access. The web suite deletes everything it creates, even on failure.
4. **Mobile covers what the app shows.** Cards are not tappable (no detail screen), so phone, email,
   contact person, channel and location cannot be asserted after saving.
5. **No mobile Allure report is included**, only the web one (`evidence/`). The mobile wrapper does write
   Allure results (output, screenshots); they were just not rendered into a report.
6. **Mobile runs against the brief's fallback company 5049209**, because creating a user for a company
   made by the web suite returned HTTP 500. The brief says that company may expire.
7. **One unexplained web flake** (WEB-08, empty Company Name once) did not recur; see
   [Known behaviour](#known-behaviour-of-the-environment).
8. **Not done (bonus):** parallel runs, web-to-mobile data handoff. The CI workflow works (see [CI](#ci-github-actions)). Known small issue:
   `ai/triage/cli.py::rerun_test` counts pytest exit code 5 (nothing collected) as a failure.

## Requirements

- Python 3.10+ (developed on 3.14)
- Chromium, installed by Playwright (below)
- [Allure Commandline](https://allurereport.org/docs/install/) to render the HTML report
  (not needed to run the tests; `allure-pytest` writes the raw results)
- For the mobile suite: Java 17+, Maestro CLI, `adb`, an emulator or device (see [docs/MOBILE_SETUP.md](docs/MOBILE_SETUP.md))

## Setup (step by step)

Commands are for Windows PowerShell; macOS/Linux differences are noted. Do the web part first; the
mobile part is only needed for the Maestro tests.

### A. Web, AI and unit tests

1. **Install Python 3.10+** from python.org (tick "Add python.exe to PATH"). Check: `python --version`.
2. **Install Git** and clone the repository:
   ```powershell
   git clone https://github.com/Lindvia/edot-qa-automation-assessment.git
   cd edot-qa-automation-assessment
   ```
3. **Create the virtual environment and install the packages:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
   If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope Process Bypass` first.
4. **Install the browser Playwright drives:** `python -m playwright install chromium`
5. **Create your `.env`** (it is gitignored, never commit it): `copy .env.example .env`, then open it
   and fill in `ESUITE_EMAIL` and `ESUITE_PASSWORD` (from the assignment brief). Leave the AI lines empty
   to use the offline Faker data; for a free AI see the next step.
6. **Optional, free AI** (test data + triage judge): create a free key at
   https://aistudio.google.com/apikey and set in `.env`:
   `AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai`, `AI_MODEL=gemini-3.5-flash-lite`,
   `AI_API_KEY=<your key>`. Groq, OpenRouter or a local Ollama work the same way (examples in `.env.example`).
7. **Check the install without touching any system:** `python -m pytest tests/unit -q` (offline; all
   tests should pass).
8. **Run the web suite** (creates and deletes one test company on eSuite): `python -m pytest web/tests`,
   or the narrower commands in [Run the web suite](#run-the-web-suite).
9. **Render the Allure report:** install the Allure Commandline (Windows: download the zip from
   https://github.com/allure-framework/allure2/releases, unzip to `C:\allure`, add `C:\allure\bin` to
   PATH; macOS: `brew install allure`), then
   ```powershell
   allure generate allure-results --clean -o allure-report
   allure open allure-report
   ```

### B. Mobile (Maestro on a real Android phone)

1. **Install Java 17** (Temurin from adoptium.net). Check: `java -version`.
2. **Install Android platform-tools** (gives `adb`): download from
   https://developer.android.com/tools/releases/platform-tools, unzip, add the folder to PATH.
   Check: `adb version`.
3. **Install the Maestro CLI:** download `maestro.zip` from https://github.com/mobile-dev-inc/maestro/releases,
   unzip to `C:\maestro`, add `C:\maestro\bin` to PATH. Check: `maestro --version`
   (macOS/Linux: `curl -Ls "https://get.maestro.mobile.dev" | bash`).
4. **Prepare the phone:** install the eWork SFA app (`id.edot.ework`); Settings, About phone, tap Build
   number 7 times; Developer options: turn on **USB debugging**, **Disable adb authorization timeout**,
   **Stay awake**, and (Realme/Oppo) **Disable permission monitoring**; turn off Battery saver; turn off
   keyboard auto-correction. Connect with a good cable in File transfer mode and tap **Allow** on the
   debugging prompt.
5. **Check the phone is reachable:** `adb devices` must list it as `device` (not `unauthorized` or
   `offline`) and `adb shell echo ok` must print `ok`.
6. **Add the mobile lines to `.env`:** `MOBILE_APP_ID=id.edot.ework`, `MOBILE_COMPANY_ID`,
   `MOBILE_USERNAME`, `MOBILE_PASSWORD` (from the brief) and, on Windows,
   `MAESTRO_CMD=C:\maestro\bin\maestro.bat`.
7. **Realme/Oppo only:** the first Maestro run asks to install its two helper apps; accept both prompts.
   The runner passes `--no-reinstall-driver`, so this happens once. Details: [docs/MOBILE_SETUP.md](docs/MOBILE_SETUP.md).
8. **Run the login tests first** (they create nothing): `python -m pytest mobile/tests/test_mobile_login.py`.
9. **Only when needed, run the customer tests:** `python -m pytest mobile/tests/test_mobile_customer.py`.
   Every run that saves a customer leaves one behind (see [Limitations](#limitations)), so do not run
   them casually. Run them from PowerShell, not Git Bash (Git Bash does not see Java).
10. **Log the phone out afterwards:** the suite does it by itself at the end of a session; if a run was
    killed, run `adb shell pm clear id.edot.ework`.

## Configuration

Everything comes from environment variables, loaded from `.env` (gitignored). **No credentials or
API keys are stored in the repository.**

| Variable | Used for |
|---|---|
| `ESUITE_URL` | eSuite base URL (default `https://esuite.edot.id`) |
| `ESUITE_EMAIL`, `ESUITE_PASSWORD` | web login (supplied with the assignment; put them in `.env`) |
| `HEADLESS` | `true` (default) or `false` to watch the browser |
| `DELETE_WAIT_SECONDS`, `EXPECT_TIMEOUT_MS` | how long a deleted company may stay in the list (default 180), and the default wait of every `expect()` (default 5000 ms). CI sets 600 and 30000 because eSuite is slower from a GitHub runner |
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
passed; in the last full customer run MOB-03 and MOB-05 passed and **MOB-04 failed**. The customer tests
take about 10 minutes (the new customer sits at the end of a ~300 card list).

**Open item, MOB-04.** MOB-04 first passed with loose "below/above the name" checks, which a
neighbouring card can satisfy. It now selects the card itself and requires each field inside it; a wrong
status fails even with similar cards on screen (checked on the phone). With the stronger check it failed:
the card showed "Jl. Gator Subroto No. 45" for the entered "Jl. Gatot Subroto No. 45". A later run
**confirmed the cause**: right after typing, the address field itself already held "Jl. Gator Subroto No. 42",
so the phone keyboard's autocorrect changed the word. Fix added, **not yet verified on a phone**: the flow
asserts the field right after typing, and the data uses plain, well-known road names. The card assertion
stays strict. The later attempts to rerun were stopped by the phone's USB connection dropping (see
[Limitations](#limitations)); they created no customer.

| Part | State |
|---|---|
| Pytest wrapper (`mobile/maestro_runner.py`, `mobile/conftest.py`): runs a flow, passes credentials as `-e` env vars, masks secrets, attaches Maestro output / debug screenshots / optional screen recording to Allure | done, tested with a fake `maestro` |
| Shared login sub-flow `flows/shared/login.yaml` (ids read from the real screen), used with `runFlow` by every flow | done, run on a phone |
| `login_success.yaml` (MOB-01), `login_wrong_password.yaml` (MOB-02: "Oops" / "Wrong login combination" / "OK") | both **pass** on a phone. Google Password Manager's "Use your saved password" sheet covers the form on launch; the shared login dismisses it ("Later") and clears each field before typing |
| `create_customer.yaml` (MOB-03, Tier 2): Basic, Locations (province > postal cascade), Documents (KTP + in-app camera photo), approval signature, confirmation, then the customer is found in the list | **passes** |
| `verify_customer_card.yaml` (MOB-04, Tier 2): the card shows the entered name, address, customer type, "Waiting for Approval" and a customer number (one assertion per field, each tied to that card) | **failed** in the last full run, fix pending verification (open item above) |
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

## CI (GitHub Actions)

`.github/workflows/tests.yml`:

- **Unit tests** (offline) run on every push and pull request.
- **Web suite** runs only when started by hand (Actions > tests > Run workflow, tick `run_web`), because
  it creates and deletes a company on the shared eSuite. It runs headless, one run at a time
  (`concurrency`), and always publishes the Allure report plus raw results as the `allure-web-report`
  artifact, even when a test fails.
- Needs repository secrets (Settings > Secrets and variables > Actions): `ESUITE_EMAIL`,
  `ESUITE_PASSWORD`; optional `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY` (without them the data is Faker).
- Status: run 37209626793 (4 Oct 2026, manual): unit 149 passed, web **13 of 13 passed** in 7 min,
  Allure report published as an artifact, no test company left on eSuite afterwards (list checked).
  Earlier runs failed on slow waits from the GitHub runner (sign-in redirect, Manage page, delete
  propagation, optional branch step); fixed with longer waits and the branch form's own copy button,
  assertions unchanged. The runner uses `EXPECT_TIMEOUT_MS=30000` and `DELETE_WAIT_SECONDS=600`.

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
