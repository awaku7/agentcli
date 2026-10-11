"""Interactive real-LLM Structured Compaction smoke-test helper (stdlib only).

Create isolated Windows launchers, capture a pre-compaction raw-history baseline,
and report persisted checkpoints without modifying the test database.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

SEED_FACTS = (
    "検証案件K17は在庫管理システムの開発です。",
    "検証案件K17ではPython 3.14を使用します。",
    "データベースはSQLiteを使用し、PostgreSQLは使いません。",
    "画面はWeb UIとし、デスクトップアプリは作りません。",
)

ENV_SETTINGS = {
    "UAGENT_SESSION_STORE": "1",
    "UAGENT_MEMORY_BACKEND": "sqlite",
    "UAGENT_STRUCTURED_COMPACTION": "1",
    "UAGENT_SHRINK_CNT": "12",
    "UAGENT_SHRINK_KEEP_LAST": "2",
    "UAGENT_SHRINK_MAX_TOKENS": "0",
    "UAGENT_SHRINK_CHUNK_TOKENS": "12000",
    "UAGENT_SUMMARY_ON_EXIT": "0",
    "UAGENT_PROFILE_ON_EXIT": "0",
    "UAGENT_ENABLE_PROFILING": "0",
    "UAGENT_SHARED_MEMORY_FILE": "",
}


def _config(run_dir: Path) -> dict[str, str]:
    config_file = run_dir / "test-config.json"
    if not config_file.is_file():
        raise ValueError(f"Missing test configuration: {config_file}")
    data = json.loads(config_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("session_db"):
        raise ValueError("Invalid test configuration")
    return data


def _test_env(config: dict[str, str]) -> dict[str, str]:
    state_dir = Path(config["state_dir"])
    env = dict(os.environ)
    env.pop("UAGENT_WORKDIR", None)
    env.update(ENV_SETTINGS)
    env.update(
        {
            "UAGENT_STATE_DIR": str(state_dir),
            "UAGENT_LOG_DIR": str(state_dir / "logs"),
            "UAGENT_SESSION_STORE_PATH": config["session_db"],
            "UAGENT_MEMORY_DB": str(state_dir / "logs" / "memory.sqlite3"),
            "UAGENT_MEMORY_FILE": str(state_dir / "logs" / "scheck_memory.jsonl"),
            "UAGENT_PROFILE_FILE": str(state_dir / "logs" / "scheck_profile.jsonl"),
        }
    )
    return env


def prepare() -> Path:
    run_dir = Path(tempfile.mkdtemp(prefix="uag-structured-live-")).resolve()
    state_dir = run_dir / "state"
    config = {
        "state_dir": str(state_dir),
        "session_db": str(state_dir / "sessions" / "sessions.sqlite3"),
        "project_dir": str(Path(__file__).resolve().parent.parent),
    }
    (run_dir / "test-config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for command, filename in (
        ("start", "01-start.cmd"),
        ("baseline", "02-baseline.cmd"),
        ("check", "03-check.cmd"),
    ):
        script = (
            "@echo off\n"
            "chcp 65001 >nul\n"
            f'"{sys.executable}" "{Path(__file__).resolve()}" '
            f'{command} --run-dir "{run_dir}"\n'
            + ("if errorlevel 1 pause\n" if command == "start" else "pause\n")
        )
        (run_dir / filename).write_text(script, encoding="utf-8")
    print("Isolated test directory:", run_dir)
    print("1. Run 01-start.cmd; answer N to any .env.sec sync prompt.")
    print("   THEN enter the FOUR seed statements.")
    for statement in SEED_FACTS:
        print("   ", statement)
    print("2. Run 02-baseline.cmd from a SECOND window before further conversation.")
    print("3. Continue the CLI conversation; run 03-check.cmd after compaction.")
    print("4. Restart with 01-start.cmd, load the previous session, and re-check.")
    print("   Checkpoint inspection produces result.md without altering the SQLite DB.")
    return run_dir


def launch(run_dir: Path) -> None:
    config = _config(run_dir)
    print("If .env.sec sync/creation is asked, type N before entering test facts.", flush=True)
    subprocess.run(
        [sys.executable, "-m", "uagent", "-C", config["project_dir"]],
        cwd=config["project_dir"],
        env=_test_env(config),
        check=True,
    )


def _db_connection(config: dict[str, str]) -> sqlite3.Connection:
    db_path = Path(config["session_db"])
    if not db_path.is_file():
        raise ValueError(f"Test session DB does not exist: {db_path}")
    # No accidental SQLite DB creation during inspection; never write the DB.
    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _messages(connection: sqlite3.Connection, session_id: str) -> list[list]:
    rows = connection.execute(
        "SELECT session_id, message_id, role, content FROM messages "
        "WHERE session_id = ? ORDER BY message_id",
        (session_id,),
    )
    return [list(row) for row in rows]


def capture_baseline(run_dir: Path) -> int:
    config = _config(run_dir)
    baseline_file = run_dir / "raw-baseline.json"
    if baseline_file.exists():
        raise ValueError("Baseline already exists; do not overwrite it.")
    with closing(_db_connection(config)) as connection:
        if connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]:
            raise ValueError("Checkpoint already exists; create a new isolated run.")
        placeholders = ",".join("?" for _ in SEED_FACTS)
        records = connection.execute(
            "SELECT session_id, content FROM messages "
            "WHERE role = 'user' AND content IN (" + placeholders + ")",
            SEED_FACTS,
        ).fetchall()
        by_session: dict[str, set[str]] = {}
        for row in records:
            by_session.setdefault(row["session_id"], set()).add(row["content"])
        matches = [
            session_id
            for session_id, facts in by_session.items()
            if all(fact in facts for fact in SEED_FACTS)
        ]
        if len(matches) != 1:
            raise ValueError(
                "Expected four seed facts in exactly one session; "
                f"matching sessions: {len(matches)}"
            )
        session_id = matches[0]
        rows = _messages(connection, session_id)
    baseline_file.write_text(
        json.dumps({"session_id": session_id, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"PASS: baseline captured ({len(rows)} messages, session {session_id})")
    return len(rows)


def _check_rows(baseline: dict, rows: list[list]) -> list[int]:
    current = {(row[0], row[1]): row for row in rows}
    return [
        old[1]
        for old in baseline["rows"]
        if current.get((old[0], old[1])) != old
    ]


def inspect(run_dir: Path) -> dict:
    config = _config(run_dir)
    baseline_file = run_dir / "raw-baseline.json"
    if not baseline_file.exists():
        raise ValueError("Capture the baseline first: 02-baseline.cmd")
    baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
    session_id = baseline["session_id"]
    with closing(_db_connection(config)) as connection:
        rows = _messages(connection, session_id)
        checkpoints = [
            dict(row)
            for row in connection.execute(
                "SELECT application_status, source_start_seq, source_end_seq, "
                "result_revision FROM checkpoints "
                "WHERE session_id = ? AND application_status = 'applied' "
                "ORDER BY result_revision, source_start_seq",
                (session_id,),
            )
        ]
        tool_count = connection.execute(
            "SELECT COUNT(*) FROM tool_calls WHERE session_id = ?", (session_id,)
        ).fetchone()[0]

    changed = _check_rows(baseline, rows)
    non_overlapping = all(
        later["source_start_seq"] > earlier["source_end_seq"]
        for earlier, later in zip(checkpoints, checkpoints[1:])
    )
    checks = {
        "initial_checkpoint": "PASS" if checkpoints else "PENDING",
        "continued_checkpoint": (
            "FAIL"
            if not non_overlapping
            else ("PASS" if len(checkpoints) >= 2 else "PENDING")
        ),
        "raw_history": "PASS" if not changed else "FAIL",
        "tool_calls_recorded": "PASS" if tool_count >= 2 else "PENDING",
    }
    report = {
        "session_id": session_id,
        "checks": checks,
        "baseline_messages": len(baseline["rows"]),
        "current_messages": len(rows),
        "lost_or_modified_ids": changed,
        "checkpoints": checkpoints,
        "tool_calls": tool_count,
    }
    lines = [
        "# UAG Structured Compaction live-test report",
        "",
        f"- Session ID: \`{session_id}\`",
        f"- Raw history: {len(baseline['rows'])} baseline / {len(rows)} now",
        f"- Lost or modified: {len(changed)} (message IDs: {changed})",
        f"- Saved tool calls: {tool_count}",
        "",
        "## Automatic SQLite checks",
        "",
        "| Check | Result |",
        "|---|---|",
        *[f"| {key} | {value} |" for key, value in checks.items()],
        "",
        "## Applied checkpoints (source intervals)",
        "",
        "| Start | End | Revision |",
        "|---:|---:|---:|",
        *[
            f"| {row['source_start_seq']} | {row['source_end_seq']} "
            f"| {row['result_revision']} |"
            for row in checkpoints
        ],
        "",
        "## Manual real-LLM checks",
        "",
        "- [ ] 回答に Python 3.14 / SQLite / PostgreSQL不使用 / Web UI が保持される",
        "- [ ] 再起動後に :sessions load で同じセッションを再開できる",
        "- [ ] 現在日時ツールと Python 計算ツールが実際に動作し、17×23=391",
        "- [ ] ツール応答と呼び出しが正しく対応し、エラーがない",
        "",
        "PENDING は実行未到達を示し、自動テストの合格ではありません。",
        "",
    ]
    (run_dir / "result.md").write_text("\n".join(lines), encoding="utf-8")
    for key, value in checks.items():
        print(f"{value}: {key}")
    print("Report:", run_dir / "result.md")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "start", "baseline", "check"))
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            prepare()
        else:
            if args.run_dir is None:
                parser.error("--run-dir is required for this command")
            if args.command == "start":
                launch(args.run_dir)
            elif args.command == "baseline":
                capture_baseline(args.run_dir)
            else:
                report = inspect(args.run_dir)
                if "FAIL" in report["checks"].values():
                    return 1
    except (OSError, ValueError, sqlite3.Error, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
