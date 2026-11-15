"""Tests for the session store's extracted-term index.

The store indexes nouns/verbs (base form) for Japanese, Chinese,
Thai and Korean messages so search can match inflected forms. The
real analyzers are optional, so most tests substitute a tiny fake
extractor with the same contract as ``text_terms``: a list of terms,
``[]`` for "processed, no terms", and ``None`` for "analyzer not
available yet".
"""

from __future__ import annotations

import importlib.util
from types import SimpleNamespace
from typing import Any

import pytest

from uagent.runtime import text_terms
from uagent.runtime.session_store import SessionStore

_SURFACE_TO_BASE = {"決めた": "決める", "合言葉": "合言葉", "バナナ": "バナナ"}


class _FakeTerms:
    def __init__(self) -> None:
        self.available = True
        self.enabled = True

    def index_terms(self, text: str) -> list[str] | None:
        if "회의" in text:  # Korean defers while its analyzer is "missing"
            return None
        if not self.available:
            return None
        return [base for surface, base in _SURFACE_TO_BASE.items() if surface in text]

    def query_terms(self, query: str) -> list[str]:
        if not self.available:
            return []
        return [_SURFACE_TO_BASE.get(query, query)] if query else []


@pytest.fixture()
def fake_terms(monkeypatch: pytest.MonkeyPatch) -> _FakeTerms:
    fake = _FakeTerms()
    monkeypatch.setattr(text_terms, "index_terms", fake.index_terms)
    monkeypatch.setattr(text_terms, "query_terms", fake.query_terms)
    monkeypatch.setattr(text_terms, "terms_enabled", lambda: fake.enabled)
    return fake


@pytest.fixture()
def store(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> SessionStore:
    # Keep searches in these tests from starting the background thread;
    # backfill behaviour is exercised through direct calls.
    monkeypatch.setattr(SessionStore, "_kick_terms_backfill", lambda self: None)
    return SessionStore(tmp_path / "sessions.sqlite3")


def _terms_by_message(store: SessionStore) -> dict[int, str]:
    rows = store._execute("SELECT message_id, terms FROM message_terms").fetchall()
    return {int(row["message_id"]): str(row["terms"]) for row in rows}


def test_append_indexes_terms_and_search_matches_base_form(
    store: SessionStore, fake_terms: _FakeTerms
) -> None:
    session = store.create_session(project="demo", entry_point="cli")
    message_id = store.append_message(
        session.session_id, "user", "昨日、合言葉はバナナに決めた"
    )

    assert _terms_by_message(store)[message_id] == "決める 合言葉 バナナ"
    hits = store.search("決める")
    assert [hit["message_id"] for hit in hits] == [message_id]
    sessions = store.search_sessions("決める")
    assert [row["session_id"] for row in sessions] == [session.session_id]


def test_unavailable_analyzer_defers_until_backfill(
    store: SessionStore, fake_terms: _FakeTerms
) -> None:
    session = store.create_session(project="demo", entry_point="cli")
    fake_terms.available = False
    message_id = store.append_message(
        session.session_id, "user", "合言葉はバナナに決めた"
    )

    assert _terms_by_message(store) == {}
    assert store.search("決める") == []
    # The literal path is unaffected by the missing analyzer.
    assert [hit["message_id"] for hit in store.search("決めた")] == [message_id]

    fake_terms.available = True
    assert store.backfill_message_terms() == 1
    assert _terms_by_message(store)[message_id] == "決める 合言葉 バナナ"
    assert [hit["message_id"] for hit in store.search("決める")] == [message_id]


def test_backfill_covers_messages_written_while_disabled(
    store: SessionStore, fake_terms: _FakeTerms
) -> None:
    session = store.create_session(project="demo", entry_point="cli")
    fake_terms.enabled = False
    message_id = store.append_message(
        session.session_id, "user", "合言葉はバナナに決めた"
    )
    assert _terms_by_message(store) == {}

    fake_terms.enabled = True
    assert store.backfill_message_terms() == 1
    assert _terms_by_message(store)[message_id] == "決める 合言葉 バナナ"


def test_backfill_skips_deferred_messages_and_processes_later_ones(
    store: SessionStore, fake_terms: _FakeTerms
) -> None:
    session = store.create_session(project="demo", entry_point="cli")
    fake_terms.available = False
    store.append_message(session.session_id, "user", "오늘 회의에서 정했다")
    japanese_id = store.append_message(
        session.session_id, "user", "合言葉はバナナに決めた"
    )

    fake_terms.available = True
    # The Korean message stays deferred (its fake analyzer never
    # arrives) but must not block the Japanese one behind it.
    assert store.backfill_message_terms() == 1
    assert list(_terms_by_message(store)) == [japanese_id]
    assert store.backfill_message_terms() == 0


def test_message_without_terms_gets_an_empty_row(
    store: SessionStore, fake_terms: _FakeTerms
) -> None:
    session = store.create_session(project="demo", entry_point="cli")
    message_id = store.append_message(session.session_id, "user", "hello world")
    assert _terms_by_message(store)[message_id] == ""
    assert store.backfill_message_terms() == 0


def test_opt_out_disables_term_matching(
    store: SessionStore, fake_terms: _FakeTerms
) -> None:
    session = store.create_session(project="demo", entry_point="cli")
    message_id = store.append_message(
        session.session_id, "user", "合言葉はバナナに決めた"
    )
    fake_terms.enabled = False
    assert store.search("決める") == []
    assert [hit["message_id"] for hit in store.search("決めた")] == [message_id]


def test_backfill_runs_alongside_appends(
    store: SessionStore, fake_terms: _FakeTerms
) -> None:
    import threading

    session = store.create_session(project="demo", entry_point="cli")
    errors: list[Exception] = []

    def do_backfill() -> None:
        try:
            for _ in range(20):
                store.backfill_message_terms()
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    thread = threading.Thread(target=do_backfill)
    thread.start()
    for index in range(20):
        store.append_message(
            session.session_id, "user", f"合言葉はバナナに決めた {index}"
        )
    thread.join(timeout=30)
    assert not thread.is_alive()
    assert errors == []
    store.backfill_message_terms()
    assert len(_terms_by_message(store)) == 20


def test_run_terms_backfill_processes_pending(
    store: SessionStore, fake_terms: _FakeTerms
) -> None:
    session = store.create_session(project="demo", entry_point="cli")
    fake_terms.available = False
    message_id = store.append_message(
        session.session_id, "user", "合言葉はバナナに決めた"
    )
    fake_terms.available = True
    store._run_terms_backfill()
    assert _terms_by_message(store)[message_id] == "決める 合言葉 バナナ"


def test_detect_script() -> None:
    assert text_terms.detect_script("これはテストです") == "ja"
    assert text_terms.detect_script("오늘 회의에서 정했다") == "ko"
    assert text_terms.detect_script("สวัสดีตอนเช้า") == "th"
    assert text_terms.detect_script("hello world") is None


def test_detect_script_cjk_only_uses_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    import uagent.i18n as i18n

    monkeypatch.setattr(i18n, "get_locale", lambda: "ja")
    assert text_terms.detect_script("会議決定事項") == "ja"
    monkeypatch.setattr(i18n, "get_locale", lambda: "en")
    assert text_terms.detect_script("会议决定事项") == "zh"


def test_janome_terms_extractor() -> None:
    tokens = [
        SimpleNamespace(
            part_of_speech="動詞,自立,*,*", base_form="決める", surface="決め"
        ),
        SimpleNamespace(
            part_of_speech="名詞,一般,*,*", base_form="*", surface="合言葉"
        ),
        SimpleNamespace(part_of_speech="助詞,格助詞,*,*", base_form="*", surface="は"),
    ]
    tokenizer = SimpleNamespace(tokenize=lambda text: tokens)
    assert text_terms._janome_terms(tokenizer, "合言葉は決めた") == ["決める", "合言葉"]


def test_kiwi_terms_extractor() -> None:
    tokens = [
        SimpleNamespace(form="회의", tag="NNG", base_form=""),
        SimpleNamespace(form="먹", tag="VV", base_form=""),
        SimpleNamespace(form="빠르", tag="VA", base_form="빠르다"),
        SimpleNamespace(form="를", tag="JKO", base_form=""),
    ]
    tokenizer = SimpleNamespace(tokenize=lambda text: tokens)
    assert text_terms._kiwi_terms(tokenizer, "회의에서 먹었다") == [
        "회의",
        "먹다",
        "빠르다",
    ]


def test_failed_analyzer_load_is_retried_after_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import time as time_module
    from types import ModuleType

    janome_pkg = ModuleType("janome")
    janome_tokenizer = ModuleType("janome.tokenizer")

    class _Token:
        part_of_speech = "動詞,自立,*,*"
        base_form = "決める"
        surface = "決め"

    class _Tokenizer:
        def tokenize(self, text: str) -> list[_Token]:
            return [_Token()]

    janome_tokenizer.Tokenizer = _Tokenizer  # type: ignore[attr-defined]
    janome_pkg.tokenizer = janome_tokenizer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "janome", janome_pkg)
    monkeypatch.setitem(sys.modules, "janome.tokenizer", janome_tokenizer)
    saved_tokenizers = dict(text_terms._tokenizers)
    saved_unavailable = dict(text_terms._unavailable)
    try:
        text_terms._tokenizers.pop("ja", None)
        # A failure recorded just now suppresses the retry...
        text_terms._unavailable["ja"] = time_module.monotonic()
        assert text_terms._load_tokenizer("ja") is None
        # ...but once the cooldown has passed, a copy that appeared
        # mid-process (e.g. via the catalog's installer) is picked up.
        text_terms._unavailable["ja"] = (
            time_module.monotonic() - text_terms._LOAD_RETRY_SECONDS - 1
        )
        assert text_terms._load_tokenizer("ja") is not None
        assert text_terms.index_terms("決めた") == ["決める"]
    finally:
        text_terms._tokenizers.clear()
        text_terms._tokenizers.update(saved_tokenizers)
        text_terms._unavailable.clear()
        text_terms._unavailable.update(saved_unavailable)


def test_index_terms_with_real_janome_when_available() -> None:
    if importlib.util.find_spec("janome") is None:
        # No analyzer installed: Japanese indexing defers (None)
        # instead of recording the message as term-less.
        assert text_terms.index_terms("昨日、会議で決めた") is None
        assert text_terms.query_terms("決める") == []
    else:
        terms = text_terms.index_terms("昨日、会議で決めた")
        assert terms is not None and "決める" in terms
