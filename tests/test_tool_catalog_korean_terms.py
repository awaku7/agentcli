"""Tests for Korean (Kiwi) terms in tool-catalog query tokenization.

The catalog tokenizer extracts nouns/verbs from Japanese, Chinese
and Thai queries; Korean queries used to fall through to whitespace
tokens. These tests use fake analyzer modules so they run without
the optional packages installed, and stub out the lazy installer so
nothing is pip-installed during the test run.
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from uagent.tools import _catalog as tools


@pytest.fixture()
def fake_kiwi(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("kiwipiepy")

    class _FakeKiwi:
        def tokenize(self, text: str) -> list[Any]:
            return [
                SimpleNamespace(form="회의", tag="NNG", base_form="회의"),
                SimpleNamespace(form="파일", tag="NNG", base_form="파일"),
                SimpleNamespace(form="를", tag="JKO", base_form="를"),
                SimpleNamespace(form="보내", tag="VV", base_form="보내"),
                SimpleNamespace(form="빠르", tag="VA", base_form="빠르다"),
            ]

    module.Kiwi = _FakeKiwi  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "kiwipiepy", module)
    monkeypatch.setattr(tools, "_auto_install", lambda *a, **k: True)
    monkeypatch.setattr(tools, "KiwiAnalyzer", None)
    monkeypatch.setattr(tools, "_kiwi_initialized", False)


def test_collect_kiwi_query_terms(fake_kiwi: None) -> None:
    # Nouns as-is, verbs/adjectives in dictionary form (stem + 다,
    # unless the analyzer already provides a distinct base form).
    assert tools._collect_kiwi_query_terms("회의 파일을 보내다") == [
        "회의",
        "파일",
        "보내다",
        "빠르다",
    ]


def test_tokenize_catalog_query_includes_korean_terms(fake_kiwi: None) -> None:
    tokens = tools._tokenize_catalog_query("회의 파일을 보내다")
    assert "회의" in tokens
    assert "파일" in tokens
    assert "보내다" in tokens


def test_korean_terms_fall_back_when_installer_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tools, "_auto_install", lambda *a, **k: False)
    monkeypatch.setattr(tools, "KiwiAnalyzer", None)
    monkeypatch.setattr(tools, "_kiwi_initialized", False)
    assert tools._collect_kiwi_query_terms("회의") == []
    # Tokenization still yields the plain whitespace tokens.
    assert "회의" in tools._tokenize_catalog_query("회의 파일")


def test_has_korean_script() -> None:
    assert tools._has_korean_script("회의 파일")
    assert not tools._has_korean_script("会議のファイル")
    assert not tools._has_korean_script("meeting files")


def test_janome_collector_accepts_japanese_pos_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real Janome reports Japanese POS labels (名詞/動詞); the
    # collector previously only accepted the English labels and so
    # never returned any terms.
    package = ModuleType("janome")
    tokenizer_module = ModuleType("janome.tokenizer")

    class _Token:
        def __init__(self, surface: str, pos: str, base: str) -> None:
            self.surface = surface
            self.part_of_speech = pos
            self.base_form = base

    class _Tokenizer:
        def tokenize(self, text: str) -> list[_Token]:
            return [
                _Token("会議", "名詞,サ変接続,*,*", "会議"),
                _Token("を", "助詞,格助詞,一般,*", "を"),
                _Token("開く", "動詞,自立,*,*", "開く"),
            ]

    tokenizer_module.Tokenizer = _Tokenizer  # type: ignore[attr-defined]
    package.tokenizer = tokenizer_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "janome", package)
    monkeypatch.setitem(sys.modules, "janome.tokenizer", tokenizer_module)
    monkeypatch.setattr(tools, "_auto_install", lambda *a, **k: True)
    monkeypatch.setattr(tools, "JanomeTokenizer", None)
    monkeypatch.setattr(tools, "_janome_initialized", False)

    assert tools._collect_janome_query_terms("会議を開く") == ["会議", "開く"]
