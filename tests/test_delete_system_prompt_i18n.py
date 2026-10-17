"""Ensure shared delete confirmations are reflected in all gettext prompts."""

from __future__ import annotations

import gettext
from pathlib import Path

import pytest

from uagent import core
from uagent.core_impl.prompt import (
    _build_system_prompt_compact,
    _build_system_prompt_full,
)

LOCALES = Path(__file__).resolve().parents[1] / "src" / "uagent" / "locales"
DELETE_POLICY = """## Dangerous operation policy (delete_file)
- For deletion using the delete_file tool, do NOT ask for confirmation before preview.
- Always run delete_file with dry_run=true first to get the list of deletion candidates.
- If there are zero candidates, do not ask; just report that nothing will be deleted.
"""


def test_delete_prompt_has_no_llm_controlled_approval_sequence():
    prompt = core.SYSTEM_PROMPT_DANGEROUS_DELETE_FILE
    for forbidden in ("confirmed=true", "human_ask", "backup globs"):
        assert forbidden not in prompt
    assert "dry_run=true" in prompt
    for full_prompt in (_build_system_prompt_compact(), _build_system_prompt_full()):
        assert prompt in full_prompt


@pytest.mark.parametrize(
    "catalog",
    sorted(LOCALES.glob("*/LC_MESSAGES/uag.mo")),
    ids=lambda p: p.parent.parent.name,
)
def test_all_locales_compile_delete_prompt_without_legacy_instructions(catalog):
    assert len(list(LOCALES.glob("*/LC_MESSAGES/uag.mo"))) == 38
    with catalog.open("rb") as stream:
        translated = gettext.GNUTranslations(stream).gettext(DELETE_POLICY)
    assert "dry_run=true" in translated
    assert "confirmed=true" not in translated
    assert "human_ask" not in translated
    assert "backup globs" not in translated
    assert len(translated.strip().splitlines()) == 4
    if catalog.parent.parent.name != "en":
        assert translated != DELETE_POLICY
