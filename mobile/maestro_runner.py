"""Run a Maestro flow from Pytest and report it into Allure.

Credentials and test data are passed to the flow as `-e KEY=VALUE` environment variables; they are
never written to a YAML file and secret values are masked wherever the command is shown or attached.
"""

import os
import shlex
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

import allure

FLOWS_DIR = Path(__file__).resolve().parent / "flows"
SECRET_KEYS = {"PASSWORD"}
MAX_DEBUG_IMAGES = 3


@dataclass
class FlowResult:
    flow: str
    returncode: int
    stdout: str
    stderr: str
    duration: float
    command: str  # secrets masked
    debug_dir: Optional[Path] = None
    video: Optional[Path] = None
    attachments: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return (self.stdout + ("\n" + self.stderr if self.stderr.strip() else "")).strip()


def mask(command: List[str]) -> str:
    """Printable command with every secret `-e KEY=VALUE` value replaced by ***."""
    shown = []
    for part in command:
        key, sep, _ = part.partition("=")
        shown.append(f"{key}=***" if sep and key in SECRET_KEYS else part)
    return " ".join(shlex.quote(p) for p in shown)


def split_command(maestro_cmd: Union[str, Sequence[str], None]) -> List[str]:
    """`maestro`, `wsl maestro` or an explicit list -> argv. Windows paths keep their backslashes."""
    if not maestro_cmd:
        return ["maestro"]
    if not isinstance(maestro_cmd, str):
        return list(maestro_cmd)
    return [part.strip('"') for part in shlex.split(maestro_cmd, posix=(os.name != "nt"))]


def build_command(maestro_cmd: Union[str, Sequence[str], None], flow: Path, env: Dict[str, str],
                  debug_dir: Path) -> List[str]:
    command = split_command(maestro_cmd)
    # --no-reinstall-driver: Maestro otherwise reinstalls its two helper apps on every run, which
    # some phones (Realme/Oppo) answer with a manual install prompt each time.
    command += ["test", "--no-reinstall-driver", "--debug-output", str(debug_dir)]
    for key, value in env.items():
        command += ["-e", f"{key}={value}"]
    command.append(str(flow))
    return command


class ScreenRecorder:
    """Best effort screen recording with `adb shell screenrecord` (needs adb on the PATH)."""

    REMOTE = "/sdcard/edot_flow.mp4"

    def __init__(self, enabled: bool):
        self.enabled = enabled and shutil.which("adb") is not None
        self._process: Optional[subprocess.Popen] = None

    def start(self) -> None:
        if self.enabled:
            self._process = subprocess.Popen(
                ["adb", "shell", "screenrecord", "--time-limit", "180", self.REMOTE],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

    def stop(self, target: Path) -> Optional[Path]:
        if not self._process:
            return None
        self._process.terminate()
        self._process.wait(timeout=15)
        pulled = subprocess.run(["adb", "pull", self.REMOTE, str(target)], capture_output=True, timeout=60)
        return target if pulled.returncode == 0 and target.exists() else None


def clear_app_session(app_id: str, timeout: int = 30) -> bool:
    """Log the app out by wiping its data (`adb shell pm clear`), so a session never leaves the phone on a
    logged-in dashboard. Needs adb on the PATH; returns False when it could not be done (no adb, or the
    phone did not answer in time)."""
    if shutil.which("adb") is None:
        return False
    try:
        run = subprocess.run(["adb", "shell", "pm", "clear", app_id], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    return run.returncode == 0 and "Success" in run.stdout


def run_flow(flow_name: str, env: Dict[str, str], maestro_cmd: Union[str, Sequence[str], None] = "maestro",
             timeout: int = 300, record: bool = False) -> FlowResult:
    """Run mobile/flows/<flow_name> and return the result (the caller decides pass/fail)."""
    flow = FLOWS_DIR / flow_name
    if not flow.exists():
        raise FileNotFoundError(f"Maestro flow not found: {flow}")

    debug_dir = Path(tempfile.mkdtemp(prefix="maestro-"))
    command = build_command(maestro_cmd, flow, env, debug_dir)
    recorder = ScreenRecorder(record)

    with allure.step(f"Maestro flow {flow_name}"):
        recorder.start()
        started = time.monotonic()
        try:
            run = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            stdout, stderr, code = run.stdout, run.stderr, run.returncode
        except subprocess.TimeoutExpired as expired:
            stdout, stderr, code = (expired.stdout or ""), f"Timed out after {timeout}s", 124
        duration = time.monotonic() - started
        video = recorder.stop(debug_dir / "recording.mp4")

        result = FlowResult(flow_name, code, stdout or "", stderr or "", duration, mask(command), debug_dir, video)
        attach_result(result)
    return result


def attach_result(result: FlowResult) -> None:
    """Attach the Maestro output, debug screenshots and the recording to the current Allure step."""
    allure.attach(f"$ {result.command}\n\nexit code {result.returncode} in {result.duration:.1f}s\n\n{result.output}",
                  name="maestro-output", attachment_type=allure.attachment_type.TEXT)
    result.attachments.append("maestro-output")
    if result.debug_dir and result.debug_dir.exists():
        shots = sorted(result.debug_dir.rglob("*.png"))[-MAX_DEBUG_IMAGES:]
        for shot in shots:
            allure.attach.file(str(shot), name=f"maestro-{shot.stem}", attachment_type=allure.attachment_type.PNG)
            result.attachments.append(f"maestro-{shot.stem}")
        for log in sorted(result.debug_dir.rglob("maestro.log"))[:1]:
            allure.attach.file(str(log), name="maestro-log", attachment_type=allure.attachment_type.TEXT)
            result.attachments.append("maestro-log")
    if result.video:
        allure.attach.file(str(result.video), name="screen-recording", attachment_type=allure.attachment_type.MP4)
        result.attachments.append("screen-recording")
