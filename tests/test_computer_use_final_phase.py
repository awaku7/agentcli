"""Opt-in integration gates for the Computer Use final phase."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from uagent.computer_use import configure_computer_use
from uagent.computer_use.runtimes.mock import MockComputerRuntime

EXPECTED_LOCALES = {
    "ar",
    "bn",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "es",
    "fa",
    "fi",
    "fil",
    "fr",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "mn",
    "mr",
    "ms",
    "nb",
    "nl",
    "nn",
    "pl",
    "pt",
    "pt_BR",
    "ro",
    "ru",
    "sv",
    "sw",
    "th",
    "tr",
    "uk",
    "vi",
    "zh_CN",
    "zh_TW",
}


class Core:
    def __init__(self):
        self.computer_use_handler = None
        self.computer_use_runtime = None


def test_all_38_locales_have_catalogs():
    root = Path(__file__).parents[1] / "src" / "uagent" / "locales"
    actual = {path.parent.parent.name for path in root.glob("*/LC_MESSAGES/uag.po")}
    assert actual == EXPECTED_LOCALES
    assert len(actual) == 38


def test_bootstrap_installs_handler_when_policy_enabled(monkeypatch):
    monkeypatch.setenv("UAGENT_COMPUTER_USE", "1")
    monkeypatch.setenv("UAGENT_COMPUTER_ALLOWED_ACTIONS", "screenshot")
    core = Core()
    runtime = MockComputerRuntime()

    handler = configure_computer_use(
        core, provider="custom", model="test-model", runtime=runtime
    )

    assert handler is core.computer_use_handler
    assert core.computer_use_runtime is runtime


@pytest.mark.skipif(
    os.getenv("UAGENT_COMPUTER_USE_API_E2E") != "1",
    reason="set UAGENT_COMPUTER_USE_API_E2E=1 to run credentialed provider E2E",
)
def test_provider_api_e2e_is_explicitly_opt_in():
    pytest.fail("Provider E2E harness must be supplied by the integration environment")


@pytest.mark.skipif(
    os.getenv("UAGENT_COMPUTER_USE_RUNTIME_E2E") != "1",
    reason="set UAGENT_COMPUTER_USE_RUNTIME_E2E=1 to run live browser/desktop E2E",
)
def test_runtime_e2e_is_explicitly_opt_in():
    pytest.fail("Live runtime harness must be supplied by the integration environment")
