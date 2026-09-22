from pathlib import Path
import re

store_path = Path("src/uagent/runtime/session_store.py")
text = store_path.read_text(encoding="utf-8")

old = '''            if "last_used_at" not in columns:\n                self._connection.execute(\n                    "ALTER TABLE sessions ADD COLUMN last_used_at TEXT"\n                )\n                self._connection.execute(\n                    "UPDATE sessions SET last_used_at = created_at WHERE last_used_at IS NULL"\n                )\n            message_columns = {'''
new = '''            if "last_used_at" not in columns:\n                self._connection.execute(\n                    "ALTER TABLE sessions ADD COLUMN last_used_at TEXT"\n                )\n                # Legacy stores used ``created_at`` as a recency timestamp when\n                # a session was loaded. Preserve that value as last-used time,\n                # then recover the original session date from the first durable\n                # message only when it predates the stored recency value.\n                self._connection.execute(\n                    "UPDATE sessions SET last_used_at = created_at WHERE last_used_at IS NULL"\n                )\n                self._connection.execute(\n                    "UPDATE sessions SET created_at = ("\n                    "SELECT MIN(m.created_at) FROM messages m "\n                    "WHERE m.session_id = sessions.session_id"\n                    ") WHERE EXISTS ("\n                    "SELECT 1 FROM messages m WHERE m.session_id = sessions.session_id "\n                    "AND m.created_at < sessions.created_at"\n                    ")"\n                )\n            self._connection.execute(\n                "CREATE INDEX IF NOT EXISTS idx_sessions_last_used "\n                "ON sessions(last_used_at DESC)"\n            )\n            self._connection.execute(\n                "CREATE INDEX IF NOT EXISTS idx_sessions_project_last_used "\n                "ON sessions(project, last_used_at DESC)"\n            )\n            message_columns = {'''
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("session migration block not found")
store_path.write_text(text, encoding="utf-8")

test_path = Path("tests/test_session_store.py")
tests = test_path.read_text(encoding="utf-8")
if '"idx_sessions_last_used"' not in tests:
    needle = '    assert {\n        "idx_messages_session_role_id",'
    replacement = (
        '    assert {\n'
        '        "idx_sessions_last_used",\n'
        '        "idx_sessions_project_last_used",\n'
        '        "idx_messages_session_role_id",'
    )
    if needle not in tests:
        raise SystemExit("session index assertion block not found")
    tests = tests.replace(needle, replacement, 1)

new_test = '''def test_legacy_session_schema_recovers_created_at_and_preserves_last_used(tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.execute("""
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            project TEXT,
            project_key TEXT NOT NULL,
            project_path TEXT,
            entry_point TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
    connection.execute("""
        CREATE TABLE messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            payload_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
    connection.execute(
        "INSERT INTO sessions(session_id, project, project_key, entry_point, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("legacy-1", "demo", "legacy-key", "cli", "2026-09-22 12:00:00"),
    )
    connection.execute(
        "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        ("legacy-1", "user", "yesterday work", "2026-09-21 09:00:00"),
    )
    connection.commit()
    connection.close()

    store = SessionStore(db_path)

    row = store.get_session("legacy-1")
    assert row["created_at"] == "2026-09-21 09:00:00"
    assert row["last_used_at"] == "2026-09-22 12:00:00"


def test_legacy_session_schema_does_not_move_creation_forward(tmp_path):
    db_path = tmp_path / "legacy-untouched.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.execute("""
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            project TEXT,
            project_key TEXT NOT NULL,
            project_path TEXT,
            entry_point TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
    connection.execute("""
        CREATE TABLE messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            payload_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
    connection.execute(
        "INSERT INTO sessions(session_id, project, project_key, entry_point, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("legacy-2", "demo", "legacy-key", "cli", "2026-09-21 08:59:00"),
    )
    connection.execute(
        "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        ("legacy-2", "user", "first message", "2026-09-21 09:00:00"),
    )
    connection.commit()
    connection.close()

    store = SessionStore(db_path)

    row = store.get_session("legacy-2")
    assert row["created_at"] == "2026-09-21 08:59:00"
    assert row["last_used_at"] == "2026-09-21 08:59:00"


'''
pattern = re.compile(
    r"def test_legacy_session_schema_migrates_last_used_at_from_created_at\(tmp_path\):\n.*?(?=def test_execute_retries_transient_database_lock)",
    re.S,
)
if pattern.search(tests):
    tests = pattern.sub(new_test, tests, count=1)
elif "def test_legacy_session_schema_recovers_created_at_and_preserves_last_used" not in tests:
    raise SystemExit("legacy migration test block not found")

test_path.write_text(tests, encoding="utf-8")
