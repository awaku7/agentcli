"""Run the improvement-design acceptance checks locally."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> bool:
    print("$", " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode == 0


def check_event_codes() -> bool:
    required = {"cli.start", "web.start", "gui.start", "a2a.task.created", "tool.dispatch", "web.room.task.started", "web.room.task.completed"}
    text = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "uagent").rglob("*.py"))
    missing = sorted(code for code in required if code not in text)
    if missing:
        print("missing event codes:", ", ".join(missing))
        return False
    return True


def check_design_artifacts() -> bool:
    required_paths = [
        "src/uagent/a2a/task_store.py",
        "src/uagent/tools/tool_policy.py",
        "src/uagent/providers/provider_caps.py",
        "src/uagent/auth/oauth_common.py",
        "src/uagent/runtime/console.py",
        "src/uagent/runtime/history.py",
        "src/uagent/runtime/logging_setup.py",
        "src/uagent/runtime/prompt_context.py",
        "scripts/check_import_graph.py",
    ]
    missing = [path for path in required_paths if not (ROOT / path).exists()]
    if missing:
        print("missing design artifacts:", ", ".join(missing))
        return False
    return True


def main() -> int:
    checks = [
        [sys.executable, "scripts/check_import_graph.py"],
        [sys.executable, "-m", "pytest", "-q", "tests"],
        [sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"],
    ]
    failed = [command for command in checks if not run(command)]
    if not check_event_codes():
        failed.append(["event-code-check"])
    if not check_design_artifacts():
        failed.append(["design-artifact-check"])

    if failed:
        print(f"acceptance: FAIL ({len(failed)} checks)")
        return 1
    print("acceptance: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
