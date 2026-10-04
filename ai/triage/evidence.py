"""Read the Allure result files and turn every failed/broken test into a Failure record."""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

FAILED_STATUSES = {"failed", "broken"}


@dataclass
class Failure:
    uuid: str
    name: str
    full_name: str
    case_id: str
    history_id: str
    status: str
    message: str
    trace: str
    steps: List[tuple]  # (depth, name, status) in execution order
    attachments: List[str]
    started: int
    history: Dict[str, int] = field(default_factory=lambda: {"passed": 0, "failed": 0})
    reruns: List[str] = field(default_factory=list)  # "passed" / "failed" per extra run

    @property
    def nodeid(self) -> Optional[str]:
        """pytest node id rebuilt from allure's fullName (module.Class#test)."""
        if "#" not in self.full_name:
            return None
        module_and_class, test = self.full_name.split("#", 1)
        parts = module_and_class.split(".")
        # the last part is the class when it starts with an upper-case letter
        cls = parts.pop() if parts and parts[-1][:1].isupper() else None
        path = "/".join(parts) + ".py"
        return f"{path}::{cls}::{test}" if cls else f"{path}::{test}"


def _label(result: dict, name: str) -> str:
    for label in result.get("labels", []):
        if label.get("name") == name:
            return label.get("value", "")
    return ""


def flatten_steps(steps: list, depth: int = 0) -> List[tuple]:
    out: List[tuple] = []
    for step in steps or []:
        out.append((depth, step.get("name", ""), step.get("status", "")))
        out.extend(flatten_steps(step.get("steps", []), depth + 1))
    return out


def _attachments(result: dict, results_dir: Path) -> List[str]:
    found = []

    def collect(item: dict) -> None:
        for attachment in item.get("attachments", []):
            found.append(f"{attachment.get('name', 'attachment')}: {results_dir / attachment.get('source', '')}")
        for step in item.get("steps", []):
            collect(step)

    collect(result)
    return found


def load_failures(results_dir: str) -> List[Failure]:
    """Latest result per test (historyId); failures also carry their pass/fail history."""
    root = Path(results_dir)
    by_history: Dict[str, List[dict]] = defaultdict(list)
    for file in root.glob("*-result.json"):
        try:
            result = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        by_history[result.get("historyId") or result.get("uuid", file.name)].append(result)

    failures: List[Failure] = []
    for history_id, results in by_history.items():
        results.sort(key=lambda r: r.get("start", 0))
        latest = results[-1]
        if latest.get("status") not in FAILED_STATUSES:
            continue
        details = latest.get("statusDetails", {}) or {}
        failure = Failure(
            uuid=latest.get("uuid", ""),
            name=latest.get("name", ""),
            full_name=latest.get("fullName", ""),
            case_id=_label(latest, "case_id"),
            history_id=history_id,
            status=latest["status"],
            message=details.get("message", "") or "",
            trace=details.get("trace", "") or "",
            steps=flatten_steps(latest.get("steps", [])),
            attachments=_attachments(latest, root),
            started=latest.get("start", 0),
        )
        failure.history["passed"] = sum(1 for r in results if r.get("status") == "passed")
        failure.history["failed"] = sum(1 for r in results if r.get("status") in FAILED_STATUSES)
        failures.append(failure)
    failures.sort(key=lambda f: f.started)
    return failures


def load_case(sheet_path: str, case_id: str) -> Optional[dict]:
    """The manual test case (expected result, data) for an id like WEB-08, from the sheet."""
    if not case_id or not Path(sheet_path).exists():
        return None
    import openpyxl

    sheet = openpyxl.load_workbook(sheet_path, read_only=True, data_only=True)["Test Cases"]
    for row in sheet.iter_rows(min_row=5, values_only=True):
        if row and row[0] == case_id:
            return {"id": row[0], "title": row[1], "data": row[4], "expected": row[5], "tier": row[6]}
    return None
