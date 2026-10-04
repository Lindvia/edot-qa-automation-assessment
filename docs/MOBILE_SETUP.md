# Mobile suite: step-by-step setup and first run

Status: the flows and the Pytest wrapper are written and unit-tested offline. **Nothing here has been
run on a device yet.** Do the steps in order; each has a check so you know it worked before moving on.

## 0. Choose a route

| Route | When | `MAESTRO_CMD` |
|---|---|---|
| **A. Native Windows** (recommended: one `adb`, no WSL) | this machine | `maestro.bat` (or the full path to it) |
| B. WSL2 | only if A fails | `wsl maestro` (needs `adb` shared into WSL, more fiddly) |
| C. macOS / Linux | another machine | `maestro` |

Use a **physical Android phone over USB** or an **Android Studio emulator**. Do not mix them.

## 1. Install Java 17+

1. Install a JDK 17 or newer (for example Temurin 17).
2. Open a new terminal and check: `java -version`. It must print 17 or higher.

## 2. Install Android platform-tools (adb)

1. Download "SDK Platform-Tools for Windows" from developer.android.com, unzip it (for example to
   `C:\platform-tools`) and add that folder to `PATH`.
2. Check in a new terminal: `adb version`.

## 3. Install Maestro

1. Download the latest `maestro.zip` from the Maestro releases page, unzip it (for example to
   `C:\maestro`) and add `C:\maestro\bin` to `PATH`.
2. Check in a new terminal: `maestro --version` (on Windows the launcher may need to be called as
   `maestro.bat`; use whichever name works in step 7).

## 4. Connect the device

Phone: Settings > About phone > tap Build number 7 times > Developer options > enable **USB debugging**,
plug in, accept the "Allow USB debugging" prompt.
Emulator: start it from Android Studio (Device Manager).

Emulator set up on the dev machine: AVD `edot_pixel` (Pixel 6, Android 34 with Google Play, x86_64).
It needs a hypervisor, so once, in an **administrator** PowerShell, then reboot:

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -NoRestart
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
```

Start it (leave the window open) with `%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe -avd edot_pixel`,
then open Play Store in the emulator, sign in, and install the eWork SFA app.

Check:

```bash
adb devices
```

It must list exactly one device with state `device` (not `unauthorized`, not `offline`).

### Realme / Oppo phones: the install prompt on every run

Maestro reinstalls its two helper apps (`dev.mobile.maestro`, `dev.mobile.maestro.test`) on every run,
and these phones ask for a manual tap each time. The runner therefore passes `--no-reinstall-driver`.
Do this once: install both with `adb install -r -t <apk>` (the APKs are inside
`C:\maestro\lib\maestro-client.jar`), tap Install on the phone, and never run `maestro hierarchy`
(it reinstalls and then removes them). Read ids with
`adb shell uiautomator dump` instead, only while no Maestro run is active.

## 5. Install the eWork SFA app and find its package id

1. Install the app on the device (Play Store or the APK you were given) and open it once.
2. Find the id:

```bash
adb shell pm list packages | findstr /i ework
```

3. If nothing matches, show what is in the foreground while the app is open:

```bash
adb shell dumpsys window | findstr /i mCurrentFocus
```

The part before the `/` is the package id. This is `MOBILE_APP_ID`.

## 6. Fill in `.env`

```
MOBILE_APP_ID=<package id from step 5>
MOBILE_COMPANY_ID=5049209
MOBILE_USERNAME=salesmanqaauto
MOBILE_PASSWORD=<password from the assignment>
MAESTRO_CMD=maestro.bat
MOBILE_RECORD=false
```

Use the fallback company 5049209: adding a user to a company created by the web suite returned HTTP 500.
Never put the password in a YAML file or in the sheet.

## 7. Smoke-check the tooling (nothing from this repo yet)

```bash
maestro.bat test --help
```

If this fails with "not found", fix `PATH` or set `MAESTRO_CMD` to the full path. If Python cannot start
`maestro.bat`, set `MAESTRO_CMD` to the full path including `.bat`.

## 8. Inspect the real screens (this replaces my guesses)

The flows currently match on visible text taken from screenshots. Confirm each one on the device:

1. Open the app on the login screen and run `maestro studio`. A browser page opens with the live
   screen and the element list.
2. Click each login field and button and note its **resource id** or **accessibility text**
   ("Company ID", "Username", "Password", "Sign In" in the current flow).
3. Log in by hand and, on the screen you land on, note one element that exists **only** on the
   dashboard. Send it to me; this fixes `DASHBOARD_TEXT` in `flows/login_success.yaml`.
4. Open New Customer Registration and note every field and button on all three steps (Basic,
   Locations, Documents), plus how you reached it from the dashboard.

Alternative without a browser: `maestro hierarchy` prints the view tree as JSON. Save one per screen.

Send me (a) the dashboard marker, (b) the ids/text per screen, (c) the path to New Customer Registration.
I will update the flows and finish MOB-03 to MOB-05.

## 9. Run the flows by hand first

```bash
maestro.bat test -e APP_ID=<id> -e COMPANY_ID=5049209 -e USERNAME=salesmanqaauto -e PASSWORD=<pw> mobile/flows/login_success.yaml
```

Expected: every step green. If a step is "Element not found", the selector is wrong: fix it from step 8,
not by adding waits.

## 10. Run through Pytest and Allure

```bash
python -m pytest mobile/tests -m mobile --clean-alluredir
allure generate allure-results -o allure-report --clean
allure open allure-report
```

Each test shows a `maestro-output` attachment, up to three Maestro screenshots, `maestro-log`, and a
`screen-recording` when `MOBILE_RECORD=true`.

## 11. Capture the evidence the brief asks for

- A run where MOB-01 and MOB-02 pass (screenshot of the Allure report).
- With `MOBILE_RECORD=true`, the recording attached to a test.
- One deliberately failing run (for example `-e PASSWORD` wrong on MOB-01) and its triage:
  `python -m ai.triage --out evidence/triage-report-mobile.md`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `adb devices` empty | cable is charge-only, USB debugging off, or the driver is missing |
| `unauthorized` | accept the prompt on the phone; or `adb kill-server` then `adb devices` |
| `Unable to launch app` | wrong `MOBILE_APP_ID` |
| `Element not found` | selector differs from the screen: inspect with `maestro studio` |
| login refused | company 5049209 or the user expired: say so in the README |
| `FileNotFoundError` for maestro | `MAESTRO_CMD` should be `maestro.bat` or a full path |
