from __future__ import annotations

from types import SimpleNamespace


def _startup_cwd() -> str:
    return '[CWD] {"event":"startup","path":"/tmp/demo"}'


def _legacy_messages() -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "system prompt"},
        {"role": "system", "content": "project instructions"},
        {"role": "system", "content": _startup_cwd()},
        {"role": "system", "content": "translated memory header\n- old rule"},
        {"role": "system", "content": "[USER PROFILE]\nold profile"},
        {"role": "system", "content": "[HOOK] keep this durable hook"},
        {"role": "user", "content": "hello"},
        {"role": "system", "content": "[MEMORY EVIDENCE]\nstale evidence"},
        {"role": "assistant", "content": "hi"},
    ]


def test_strip_derived_memory_context_handles_legacy_startup_order() -> None:
    from uagent.runtime.memory_history_boundary import strip_derived_memory_context

    filtered = strip_derived_memory_context(_legacy_messages())
    contents = [str(message.get("content") or "") for message in filtered]

    assert contents == [
        "system prompt",
        "project instructions",
        _startup_cwd(),
        "[HOOK] keep this durable hook",
        "hello",
        "hi",
    ]


class _FakeStore:
    def __init__(self) -> None:
        self.messages = {"s1": _legacy_messages()}
        self.replace_calls: list[tuple[str, list[dict[str, str]]]] = []
        self.sql: list[str] = []

    def list_sessions(self):
        return [{"session_id": "s1"}]

    def list_messages(self, session_id: str):
        return [dict(message) for message in self.messages[session_id]]

    def replace_messages(self, session_id: str, messages):
        copied = [dict(message) for message in messages]
        self.replace_calls.append((session_id, copied))
        self.messages[session_id] = copied

    def search(self, query: str, *, project=None, limit: int = 20):
        del query, project, limit
        return [
            {"session_id": "s1", "role": "system", "content": "old memory"},
            {"session_id": "s1", "role": "user", "content": "user fact"},
        ]

    def _execute(self, sql: str, parameters=()):
        del parameters
        self.sql.append(sql)
        return SimpleNamespace()


def test_attached_session_store_boundary_filters_read_replace_and_search() -> None:
    from uagent.runtime.memory_history_boundary import (
        install_session_store_memory_boundary,
    )

    store = _FakeStore()
    core = SimpleNamespace(session_store=store)
    install_session_store_memory_boundary(core)

    assert [message["content"] for message in store.list_messages("s1")] == [
        "system prompt",
        "project instructions",
        _startup_cwd(),
        "[HOOK] keep this durable hook",
        "hello",
        "hi",
    ]

    store.replace_messages("s1", _legacy_messages())
    persisted = store.messages["s1"]
    assert all("old rule" not in message["content"] for message in persisted)
    assert all(
        not message["content"].startswith("[USER PROFILE]") for message in persisted
    )
    assert all(
        not message["content"].startswith("[MEMORY EVIDENCE]") for message in persisted
    )

    assert store.search("fact") == [
        {"session_id": "s1", "role": "user", "content": "user fact"}
    ]


def test_runtime_log_boundary_reinstalls_after_logger_replacement() -> None:
    from uagent.runtime.runtime_memory import (
        _ensure_memory_log_boundary,
        _register_memory_system_content,
    )

    first_log: list[dict[str, str]] = []
    second_log: list[dict[str, str]] = []
    core = SimpleNamespace(log_message=first_log.append)

    _ensure_memory_log_boundary(core)
    memory = "translated memory header\n- transient"
    _register_memory_system_content(core, "personal", memory)
    core.log_message({"role": "system", "content": memory})
    core.log_message({"role": "system", "content": "[USER PROFILE]\ntransient"})
    core.log_message({"role": "user", "content": "keep me"})

    assert first_log == [{"role": "user", "content": "keep me"}]

    core.log_message = second_log.append
    _ensure_memory_log_boundary(core)
    core.log_message({"role": "system", "content": memory})
    core.log_message({"role": "user", "content": "keep me too"})

    assert second_log == [{"role": "user", "content": "keep me too"}]


def test_forget_physically_purges_legacy_projection_using_raw_store_methods() -> None:
    from uagent.runtime.memory_forget import invalidate_memory_runtime
    from uagent.runtime.memory_history_boundary import (
        install_session_store_memory_boundary,
    )

    store = _FakeStore()
    core = SimpleNamespace(
        session_store=store,
        memory_generation=0,
        _uagent_memory_system_contents={
            "personal": {"translated memory header\n- old rule"}
        },
        responses_state={},
    )
    install_session_store_memory_boundary(core)

    assert invalidate_memory_runtime(core) == 1

    raw_messages = store.messages["s1"]
    assert [message["content"] for message in raw_messages] == [
        "system prompt",
        "project instructions",
        _startup_cwd(),
        "[HOOK] keep this durable hook",
        "hello",
        "hi",
    ]
    assert store.replace_calls
    assert "DELETE FROM response_states" in store.sql
    assert "DELETE FROM session_summaries" in store.sql


def test_restore_plan_never_reintroduces_derived_memory() -> None:
    from uagent.runtime.session_command_service import (
        SessionCommandService,
        SessionContextState,
    )

    state = SessionContextState(tool_context={}, response_state=None, agent_state=None)
    plan = SessionCommandService(object()).build_restore_plan(
        "s1",
        _legacy_messages(),
        system_prompt="fallback system",
        state=state,
    )

    contents = [str(message.get("content") or "") for message in plan.messages]
    assert "translated memory header\n- old rule" not in contents
    assert not any(content.startswith("[USER PROFILE]") for content in contents)
    assert not any(content.startswith("[MEMORY EVIDENCE]") for content in contents)
    assert "hello" in contents
