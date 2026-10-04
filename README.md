# eDOT QA Automation take-home

Python + Pytest + Playwright (web), Allure reporting, and AI inside the suite (test data and failure
triage). Target: eSuite (`https://esuite.edot.id`). See [AI_USAGE.md](AI_USAGE.md) for how AI is used
and `docs/edot-test-cases.xlsx` for the manual test cases (Phase 1).

> **Status.** Web suite, AI test-data module, AI failure triage and the test-case sheet are done and
> verified (web: 13/13 passed locally and in GitHub Actions). The **mobile (Maestro) suite runs on a real
> phone**: MOB-01 to MOB-05 have each passed; MOB-03 and MOB-04 passed together in the last customer run
> (see [Mobile](#mobile-maestro--pytest) and [Limitations](#limitations)).
> The evidence (full web Allure report, triage report with the AI judge) is in [`evidence/`](#evidence-in-this-repo-evidence).

## Contents

- [Limitations](#limitations) · [Beginner guide](#beginner-guide) (blocked? other computer/phone? iPhone? AI? improvements)
- [Requirements](#requirements) · [Setup](#setup-step-by-step) · [Configuration](#configuration)
- [Run the web suite](#run-the-web-suite) · [Unit tests](#unit-tests-offline)
- [Allure report](#allure-report)
- [AI failure triage](#ai-failure-triage) · [Triage evidence](#triage-evidence)
- [Mobile](#mobile-maestro--pytest) · [CI](#ci-github-actions)
- [Project layout](#project-layout) · [Engineering rules](#engineering-rules) · [Known behaviour of the environment](#known-behaviour-of-the-environment)

## Limitations

Read these first; they are the honest gaps of this submission.

1. **MOB-04 failed once, then passed after a data fix.** The phone keyboard autocorrected a typed
   street ("Gatot" became "Gator"; confirmed from the saved screen dump). Fix: `create_customer.yaml` now
   asserts the address field right after typing, and the AI prompt and Faker fallback use plain,
   well-known road names. MOB-03 and MOB-04 then passed together on 4 Oct 2026. The card assertion was never
   weakened. One passing run is thin evidence: autocorrect could still change another street.
2. **Mobile runs depend on the phone staying connected.** On the Realme test phone adb lost its USB
   debugging authorization or went offline every 10-15 minutes, so several attempts could not
   finish. This is a device/USB problem, not a suite result. The runner now checks that the phone answers
   `adb shell echo ok` within 15 seconds before a session and stops with a clear message instead of
   hanging. The run that finally passed used **adb over Wi-Fi** (`adb tcpip 5555`, `adb connect <phone ip>:5555`,
   `ANDROID_SERIAL` and `MAESTRO_CMD=maestro --device <ip>:5555`), which avoids the USB drops. The emulator
   could not be used (this PC has no hypervisor).
3. **Mobile test data cannot be cleaned.** The app has no delete for customers, so every run that saves
   a customer leaves one in the shared company 5049209 (list in the [Mobile](#mobile-maestro--pytest)
   section: CUST-00287, 00289, 00290, 00291, "Toko Berkah Utama QABPCSG" from the passing run, and 00288 unconfirmed). They need someone with eSuite
   customer-management access. The web suite deletes everything it creates, even on failure.
4. **Mobile covers what the app shows.** Cards are not tappable (no detail screen), so phone, email,
   contact person, channel and location cannot be asserted after saving.
5. **The mobile Allure report merges separate sessions.** `evidence/allure-mobile-report/` has one result
   per mobile test (5 of 5), but they come from different sessions: MOB-03/MOB-04 from the passing customer run,
   MOB-01/MOB-02/MOB-05 from a later run that creates no data. Failed and hung attempts from earlier in the day
   are not in it; they are described under item 1 and 2. The phone can only run one flow at a time, so the report
   is not a single continuous run.
6. **Mobile runs against the brief's fallback company 5049209**, because creating a user for a company
   made by the web suite returned HTTP 500. The brief says that company may expire.
7. **The earlier web flake (WEB-08, "Next stays disabled") is explained and fixed:** the app rejects a Company
   Name over 30 characters and an AI-generated name was too long; see
   [Known behaviour](#known-behaviour-of-the-environment).
8. **Bonus items not done, and why:**
   - **Parallel execution: not done on purpose.** The lifecycle tests run in a fixed order and share one
     company (create, verify, delete), the whole run shares one login session, and everything works on the same
     shared eSuite. Running tests in parallel would break that order or let two runs create and delete at the
     same time, with one run's cleanup touching another's data (against the "no data left behind" rule). The
     mobile suite has one phone, so it cannot run in parallel at all. The CI workflow does serialise runs
     (`concurrency`).
   - **Web-to-mobile data handoff: blocked by the app.** Creating a user for a company made by the web suite
     returned HTTP 500 "error in account center" even with unique values, so the mobile app cannot log into
     the new company. Mobile therefore uses the brief's fallback company 5049209 (item 6). It could be done
     if eDOT fixes that call or names another way to create the mobile user.
   - **Mobile screen recording: not working on the test phone.** `MOBILE_RECORD=true` makes the wrapper run
     `adb shell screenrecord` and attach the video, but the Realme (Android 16) refuses to let the adb shell
     user write a video anywhere (`Permission denied` on `/sdcard`, `/sdcard/Download`, `/sdcard/Movies` and
     `/data/local/tmp`), so no video is attached; the run just continues. The Allure report has the Maestro
     output, the Maestro log and debug screenshots instead. On a phone or emulator that allows it, the
     recorder may need a proper stop (the file must be finalized) before the video is usable; not verified.
   - **CI pipeline: done** (see [CI](#ci-github-actions)).
   - Known small issue: `ai/triage/cli.py::rerun_test` counts pytest exit code 5 (nothing collected) as a failure.

## Beginner guide

For someone new to test automation or new to this repository. "Verified" below means it was run on this
project; "my understanding" means it was not tested here, so check the linked docs before relying on it.

### How the pieces fit together

| Piece | What it does | Where |
|---|---|---|
| **Pytest** | finds and runs the tests, reports pass/fail | `web/tests`, `mobile/tests`, `tests/unit` |
| **Playwright** | drives a real Chromium browser for the web tests | `web/pages` (one class per page, the "page object") |
| **Maestro** | taps and types on a real Android phone from small YAML files | `mobile/flows` |
| **Allure** | turns the raw results into a clickable HTML report | `evidence/allure-*-report` |
| **AI test data** | an AI model invents realistic company/customer data; a schema checks it; Faker is the fallback | `ai/data_generator.py` |
| **AI failure triage** | after a run, walks the evidence of each failure and proposes a verdict (script defect, product bug, flaky) | `ai/triage` |
| **GitHub Actions** | runs the unit tests on every push, and the web suite on demand | `.github/workflows/tests.yml` |

The idea of every important test: **create** something, **verify** the data is really there (not just a
"saved" message), then **delete** it. Data is never left on the shared system, except where the app gives no
way to delete (see [Limitations](#limitations)).

### If you are blocked

Work top to bottom; stop at the first line that matches.

| What you see | Most likely cause | What to do |
|---|---|---|
| `pip install` or `playwright install` fails | no internet, or an old Python | check `python --version` is 3.10+, retry on another network |
| Every web test errors at login | wrong or missing `ESUITE_EMAIL` / `ESUITE_PASSWORD` in `.env` | fix `.env` (never type them into a file that is committed); run `python -m pytest -m smoke` |
| Web tests pass locally but fail in GitHub Actions on timeouts | eSuite is slower from a GitHub runner | raise `EXPECT_TIMEOUT_MS` / `DELETE_WAIT_SECONDS` in the workflow (this is how CI was made green) |
| A web run failed halfway | a test company may be left on eSuite | open eSuite > Companies and look for names ending in `QA` plus 4-8 capital letters; delete only those. The lifecycle test normally cleans up by itself |
| `Phone not reachable over adb` (the run stops at once) | phone locked, cable out, or USB debugging authorization lost | unlock the phone, replug, tap Allow on the debugging prompt, check `adb devices` shows `device` and `adb shell echo ok` prints `ok` |
| `adb devices` shows `unauthorized` or `offline` | the phone dropped the USB debugging session (happened every 10-15 min on the test Realme) | turn USB debugging off/on; or use adb over Wi-Fi (Setup, part B, step 5), which avoided the drops |
| Maestro seems frozen | adb stopped answering, so Maestro waits silently | stop the run (`Get-Process java,python \| Stop-Process`), fix the connection, start again |
| `JAVA_HOME` error or exit code 9009 | Java is not visible (typical in Git Bash) | run from PowerShell with Java 17 installed |
| Phone asks to install Maestro helper apps each run | Realme/Oppo install prompt | accept once; the runner already passes `--no-reinstall-driver` ([docs/MOBILE_SETUP.md](docs/MOBILE_SETUP.md)) |
| MOB-04 fails on the address | keyboard autocorrect changed the typed text | turn autocorrect off on the phone; the flow now fails right after typing with a clear message |
| AI data says `source: faker` | no AI key, rate limit (HTTP 429), or the endpoint is down | read the `note` in the `company-test-data` attachment; set `AI_*` in `.env` or accept the Faker fallback |
| The mobile run left the phone logged in | the run was killed before the logout fixture | `adb shell pm clear id.edot.ework` |

**Rule of thumb when blocked:** do not weaken an assertion, skip a test, or lengthen a wait without knowing
why it failed. Read the failure screenshot and message first (the Allure report attaches them), then decide
whether the cause is the test, the environment or the product.

### Run it on another computer, Android phone or emulator

You need the same things as in [Setup](#setup-step-by-step), on that machine:

1. **Python 3.10+, Git, the repo and its `.env`** (copy `.env.example`; the values come from the brief; the
   `.env` file never goes into Git).
2. **Web only:** `pip install -r requirements.txt` and `python -m playwright install chromium`. Works on
   Windows, macOS and Linux (verified: Windows 11 locally and Ubuntu in GitHub Actions).
3. **Android phone:** Java 17, `adb`, the Maestro CLI, USB debugging on, the eWork app installed, and a
   data cable (or the same Wi-Fi for adb over Wi-Fi). Set `MAESTRO_CMD` to the Maestro path if it is not on PATH.
4. **Android emulator instead of a phone:** install Android Studio, create a virtual device, start it, and
   `adb devices` should list it as `emulator-5554`. It needs hardware virtualization (on Windows: enable it in
   the BIOS, plus Windows Hypervisor Platform). That was not available on the machine used here, which is why
   a real phone was used. The eWork app must be installed in the emulator by hand (sideload the APK).
5. **Different phone model:** the flows use the app's own resource ids (`id.edot.ework:id/...`), so they work
   on any Android phone running the same app version. What differs per phone: the permission and install prompts,
   the keyboard (autocorrect!), and the camera screen. Expect to adjust the optional "Later" and install-prompt steps.
6. **Another app version:** if a screen changes, ids may change. Inspect the screen again (see
   [docs/MOBILE_SETUP.md](docs/MOBILE_SETUP.md)) and update only the id in `mobile/flows`.

### What about an iPhone?

Not supported by this repository, and not tested. My understanding, to be checked against the
[Maestro iOS docs](https://docs.maestro.dev/):

- Maestro's open-source CLI runs iOS flows on the **iOS Simulator**, which needs a **Mac with Xcode**. Real iPhones
  are, as far as I know, not supported by the free CLI.
- The flows would need rewriting: they select by Android resource ids, which iOS apps do not have. iOS uses
  accessibility labels or visible text, so every selector would have to be re-read from the iOS app.
- It also needs the iOS build of the eWork app (a different app id) and a way to install it in the Simulator;
  whether such a build is available to us is unknown.
- What would carry over unchanged: the Pytest wrapper, the AI data module, the logout idea (reinstalling the app
  or resetting the simulator instead of `pm clear`), and the reporting.

For real-device and iOS coverage without owning the hardware, a device cloud (for example Maestro Cloud,
BrowserStack or Firebase Test Lab) is the usual route; none of them has been tried here.

### Using the AI more

What the AI does here is deliberately small and guarded (details in [AI_USAGE.md](AI_USAGE.md)):

- **Test data**: the model proposes values, a JSON schema validates them, one retry is allowed, then Faker takes
  over. The test never trusts the model.
- **Triage**: rules check the evidence first; the model is asked only at step 4 ("was the expected value itself
  right?"). It proposes a verdict; it never edits a test, never changes an assertion and never files a bug.

How to use it more, safely:

1. **Switch provider or model** only in `.env` (`AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY`): Gemini free tier
   (used here), Groq, OpenRouter, a local Ollama (no key, no data leaves the machine), or Anthropic. Free tiers
   rate-limit bursts; the Faker fallback covers that.
2. **Add a field to the generated data**: add it to the schema (`ai/schemas.py`) and the prompt
   (`ai/data_generator.py`), and a unit test for the rejected values. The schema is the safety net, so change it first.
3. **Run triage after every CI run**: add `python -m ai.triage` as a step after the tests and upload the Markdown
   report next to the Allure report. It reads `allure-results`, so no other change is needed.
4. **Ideas that fit the same guardrails** (not built): draft test cases from a spec for a human to review,
   summarise a flaky test's history, suggest a replacement locator when one stops resolving (as a suggestion in
   a report, never an automatic edit), group many failures by root cause.
5. **Do not**: send real customer data or secrets to a model, let the model change assertions or expected values,
   or treat a model answer as a verdict without the evidence next to it.

### What to improve next

Roughly by value:

1. **Remove the leftover mobile customers** and ask eDOT for a delete (or a test-data reset) for customers; then
   mobile can meet the "no data left behind" rule fully.
2. **A stable device setup**: a dedicated test phone with debugging authorization that does not expire, or an
   emulator on a machine with virtualization; then mobile tests can run in CI like the web ones.
3. **Fix the web-to-mobile handoff** with eDOT (the user-creation call returns HTTP 500 for new companies), so mobile
   logs into the company the web suite created and the fallback company is not needed.
4. **Assert more on mobile** once the app has a customer detail screen (phone, email, channel and location are not
   shown today).
5. **Parallel runs** for the independent web tests only (display and negative tests), with the data-creating tests
   kept serial.
6. **Publish the Allure report** from CI to GitHub Pages instead of an artifact, and keep the history trend.
7. **Fix `rerun_test`** in `ai/triage/cli.py` (it counts pytest exit code 5, nothing collected, as a failure).
8. **Probe the other form limits** the way the 30-character name limit was found (the customer outlet name in
   the mobile app is still unprobed), and save a Playwright trace on failure.

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
5. **Optional, more stable: adb over Wi-Fi.** With the phone on USB and the same Wi-Fi as the PC: `adb tcpip 5555`, then `adb connect <phone ip>:5555` (`adb shell ip route` shows the ip). Then in PowerShell set `$env:ANDROID_SERIAL="<ip>:5555"` and `$env:MAESTRO_CMD="C:\maestro\bin\maestro.bat --device <ip>:5555"`. Back to USB: `adb -s <ip>:5555 usb`.
5b. **Check the phone is reachable:** `adb devices` must list it as `device` (not `unauthorized` or
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
| `DELETE_WAIT_SECONDS`, `EXPECT_TIMEOUT_MS` | how long a deleted company may stay in the list (default 600; measured 284 s), and the default wait of every `expect()` (default 5000 ms). CI sets 30000 for `EXPECT_TIMEOUT_MS` because eSuite is slower from a GitHub runner |
| `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY` | optional free AI: any OpenAI-compatible endpoint (Groq, Gemini, OpenRouter, a local Ollama). `AI_API_KEY` is not needed for Ollama. Examples are in `.env.example` |
| `ANTHROPIC_API_KEY` | optional alternative, used only when `AI_BASE_URL` is empty |
| none of the above | test data falls back to Faker and triage runs rules-only |
| `FAKER_SEED` | seed of the offline fallback |
| `MOBILE_APP_ID`, `MOBILE_COMPANY_ID`, `MOBILE_USERNAME`, `MOBILE_PASSWORD` | mobile login (password never in a YAML file) |
| `MAESTRO_CMD`, `MOBILE_RECORD`, `MOBILE_FLOW_TIMEOUT` | how to call Maestro (on Windows the full path to `maestro.bat`), optional screen recording (not working on the test phone, see Limitations), per-flow timeout |

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
| `allure-mobile-report/` | Allure report of the 5 mobile tests, all passed on 4 Oct 2026 (Realme phone, adb over Wi-Fi). It merges two sessions: MOB-03/MOB-04 from the customer run and MOB-01/02/05 from a later run that creates no data. Maestro output, debug screenshots and the Maestro log are attached; the password is redacted from the attachments. |

The mobile report covers separate phone sessions (see [Limitations](#limitations) item 5 and
[Mobile](#mobile-maestro--pytest) for the state of each test).

One intermittent failure was seen early on: Next stayed disabled in the Register Company wizard (WEB-08,
and WEB-09/WEB-12 failed on their precondition). The cause was found later by probing the form: the app
rejects a Company Name over 30 characters, and an AI-generated name plus the unique suffix was sometimes
longer. The data module now limits the name (schema, prompt and Faker fallback, with unit tests).

## Mobile (Maestro + Pytest)

**State on a real phone (Realme, Android 16, fallback company 5049209), 4 Oct 2026:** MOB-01 and MOB-02
passed; MOB-03 and MOB-04 passed together in the last customer run (about 8 minutes, over adb Wi-Fi) and
MOB-05 passed earlier. The new customer sits at the end of a ~300 card list.

**History of MOB-04.** It first passed with loose "below/above the name" checks, which a neighbouring card
can satisfy. It now selects the card itself and requires each field inside it; a wrong status fails even
with similar cards on screen (checked on the phone). With the stronger check it failed: the card showed
"Jl. Gator Subroto No. 45" for the entered "Jl. Gatot Subroto No. 45". A later run confirmed the cause:
right after typing, the address field itself already held "Jl. Gator Subroto No. 42" (keyboard autocorrect).
Fix: the flow asserts the field right after typing, and the data uses plain, well-known road names. The
card assertion stayed strict, and MOB-03 + MOB-04 then passed.

| Part | State |
|---|---|
| Pytest wrapper (`mobile/maestro_runner.py`, `mobile/conftest.py`): runs a flow, passes credentials as `-e` env vars, masks secrets, attaches Maestro output / debug screenshots / optional screen recording to Allure | done, tested with a fake `maestro` |
| Shared login sub-flow `flows/shared/login.yaml` (ids read from the real screen), used with `runFlow` by every flow | done, run on a phone |
| `login_success.yaml` (MOB-01), `login_wrong_password.yaml` (MOB-02: "Oops" / "Wrong login combination" / "OK") | both **pass** on a phone. Google Password Manager's "Use your saved password" sheet covers the form on launch; the shared login dismisses it ("Later") and clears each field before typing |
| `create_customer.yaml` (MOB-03, Tier 2): Basic, Locations (province > postal cascade), Documents (KTP + in-app camera photo), approval signature, confirmation, then the customer is found in the list | **passes** |
| `verify_customer_card.yaml` (MOB-04, Tier 2): the card shows the entered name, address, customer type, "Waiting for Approval" and a customer number (one assertion per field, each tied to that card) | **passes** (after the autocorrect fix above) |
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
  runs: at least CUST-00287 (a manual probe, "Toko QA Probe"), CUST-00289, CUST-00290, CUST-00291 and "Toko Berkah Utama QABPCSG" (the passing run; its CUST number was not
  read)** (CUST-00288 is unconfirmed). They need to be removed by someone with access to the customer
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
  assertions unchanged. The runner uses `EXPECT_TIMEOUT_MS=30000` (`DELETE_WAIT_SECONDS` default 600).

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
  the company left the complete list only after about 284 seconds in a measured run (an earlier
  "31 seconds" was a false reading: the list loads in batches, so a company can look missing while the list
  is still loading; the page now waits until the list stops growing). The delete test reloads the list until
  `DELETE_WAIT_SECONDS` runs out and attaches the measured delay.
- **Company Name accepts at most 30 characters.** A longer name keeps Next disabled (found by probing the form).
  The generated name gets " QA" + 5 letters appended, so the data module keeps the name it asks for to 22
  characters. This was the cause of the earlier unexplained WEB-08 "Next stays disabled" flake.
- **A new company's detail page can stay blank for a moment.** The test reloads it a few times before
  asserting the data.
- **The UI differs between app versions** (for example the Companies header, and the optional branch
  step of the registration wizard). The tests assert only what the test cases promise.
- **Logins:** a wrong password shows "Incorrect password" followed by a per-request reference code
  (only the prefix is asserted); an unknown email and an unknown username show different dialogs.
