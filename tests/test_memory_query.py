from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_concrete_request_does_not_mix_stale_context() -> None:
    from uagent.runtime.memory_query import build_memory_retrieval_query

    core = SimpleNamespace(
        get_agent_state=lambda: {
            "goal": "old database migration",
            "current_step": "old step",
        }
    )
    messages = [
        {"role": "user", "content": "repair the database"},
        {"role": "assistant", "content": "done"},
        {"role": "user", "content": "explain OAuth tokens"},
    ]

    query = build_memory_retrieval_query(messages, core, project="legacy-project")

    assert query.text == "explain OAuth tokens"
    assert query.sources == ("latest_user",)
    assert query.context_enriched is False


def test_continuation_request_uses_previous_turn_state_and_project() -> None:
    from uagent.runtime.memory_query import build_memory_retrieval_query

    core = SimpleNamespace(
        get_agent_state=lambda: {
            "goal": "complete the UAG memory architecture",
            "current_step": "implement contextual retrieval",
            "next_action": "run memory tests",
        }
    )
    messages = [
        {"role": "user", "content": "Improve memory retrieval for UAG"},
        {"role": "assistant", "content": "ready"},
        {"role": "user", "content": "その件を続けて"},
    ]

    query = build_memory_retrieval_query(messages, core, project="agentcli")

    assert query.text.splitlines() == [
        "その件を続けて",
        "Improve memory retrieval for UAG",
        "complete the UAG memory architecture",
        "implement contextual retrieval",
        "run memory tests",
        "agentcli",
    ]
    assert query.sources == (
        "latest_user",
        "previous_user",
        "agent_goal",
        "agent_current_step",
        "agent_next_action",
        "project",
    )
    assert query.context_enriched is True


def test_contextual_query_is_bounded_and_deduplicated() -> None:
    from uagent.runtime.memory_query import build_memory_retrieval_query

    core = SimpleNamespace(
        get_agent_state=lambda: {
            "goal": "same subject",
            "current_step": "same subject",
            "next_action": "X" * 200,
        }
    )
    messages = [
        {"role": "user", "content": "same subject"},
        {"role": "user", "content": "continue"},
    ]

    query = build_memory_retrieval_query(
        messages,
        core,
        project="same subject",
        max_chars=40,
    )

    assert len(query.text) <= 40
    assert query.text.splitlines() == ["continue", "same subject"]
    assert query.sources == ("latest_user", "previous_user")


@pytest.mark.parametrize(
    ("locale", "phrase"),
    [
        ("ar", "تابع"),
        ("bn", "চালিয়ে যান"),
        ("cs", "pokračujte"),
        ("da", "fortsæt"),
        ("de", "weiter"),
        ("el", "συνεχίστε"),
        ("en", "continue"),
        ("es", "continúa"),
        ("fa", "ادامه دهید"),
        ("fi", "jatka"),
        ("fil", "magpatuloy"),
        ("fr", "continuez"),
        ("he", "המשך"),
        ("hi", "जारी रखें"),
        ("hu", "folytasd"),
        ("id", "lanjutkan"),
        ("it", "continua"),
        ("ja", "続けて"),
        ("ko", "계속해 주세요"),
        ("mn", "үргэлжлүүл"),
        ("mr", "सुरू ठेवा"),
        ("ms", "teruskan"),
        ("nb", "fortsett"),
        ("nl", "doorgaan"),
        ("nn", "hald fram"),
        ("pl", "kontynuuj"),
        ("pt", "continue"),
        ("pt_BR", "continue"),
        ("ro", "continuă"),
        ("ru", "продолжай"),
        ("sv", "fortsätt"),
        ("sw", "endelea"),
        ("th", "ดำเนินการต่อ"),
        ("tr", "devam et"),
        ("uk", "продовжуй"),
        ("vi", "tiếp tục"),
        ("zh_CN", "继续"),
        ("zh_TW", "繼續"),
    ],
)
def test_continuation_detection_supports_all_locales(locale: str, phrase: str) -> None:
    from uagent.runtime.memory_query import (
        CONTINUATION_TERMS_BY_LOCALE,
        build_memory_retrieval_query,
    )

    assert len(CONTINUATION_TERMS_BY_LOCALE) == 38
    assert CONTINUATION_TERMS_BY_LOCALE[locale] == phrase

    messages = [
        {"role": "user", "content": "database migration plan"},
        {"role": "assistant", "content": "ready"},
        {"role": "user", "content": phrase},
    ]

    query = build_memory_retrieval_query(messages, SimpleNamespace())

    assert query.context_enriched is True
    assert "database migration plan" in query.text.splitlines()


def test_projection_finds_goal_for_generic_continuation(tmp_path, monkeypatch) -> None:
    from uagent.runtime.memory_projection import (
        apply_memory_projection,
        prepare_memory_projection,
    )
    from uagent.tools import long_memory

    monkeypatch.setenv("UAGENT_MEMORY_PROJECTION", "1")
    monkeypatch.setenv("UAGENT_MEMORY_PROJECT", tmp_path.name)
    monkeypatch.setattr(
        long_memory,
        "load_long_memory_records",
        lambda: [{"note": "UAG memory architecture uses stable source IDs"}],
    )
    core = SimpleNamespace(
        get_agent_state=lambda: {"goal": "complete the UAG memory architecture"}
    )
    messages = [{"role": "user", "content": "continue"}]

    snapshot = prepare_memory_projection(messages, core)
    projected = apply_memory_projection(messages, snapshot, core)

    assert snapshot is not None
    evidence = [
        str(message.get("content") or "")
        for message in projected
        if str(message.get("content") or "").startswith("[MEMORY EVIDENCE]")
    ]
    assert len(evidence) == 1
    assert "stable source IDs" in evidence[0]
    assert snapshot.diagnostics["query_context_enriched"] is True
    assert snapshot.diagnostics["query_sources"] == [
        "latest_user",
        "agent_goal",
        "project",
    ]
    assert "UAG memory architecture" not in str(snapshot.to_diagnostics())
