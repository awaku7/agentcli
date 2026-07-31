# -*- coding: utf-8 -*-
"""Catalog-before-answer steering is omitted under native GPT-5.4 tool_search."""

from __future__ import annotations

import os
import unittest
from unittest import mock


class CatalogSteeringGateTests(unittest.TestCase):
    def setUp(self) -> None:
        # Isolate env that affects mode / model detection.
        self._env_patch = mock.patch.dict(
            os.environ,
            {
                "UAGENT_GPT54_TOOL_SEARCH": "native",
                "UAGENT_MODEL": "gpt-5.4",
                "UAGENT_PROVIDER": "openai",
            },
            clear=False,
        )
        self._env_patch.start()

    def tearDown(self) -> None:
        self._env_patch.stop()

    def test_should_emit_false_for_native_gpt54(self) -> None:
        from uagent.tools.llm_tool_narrowing import should_emit_catalog_steering

        self.assertFalse(
            should_emit_catalog_steering(
                provider="openai",
                depname="gpt-5.4",
                use_responses_api=True,
            )
        )

    def test_should_emit_true_for_nano(self) -> None:
        from uagent.tools.llm_tool_narrowing import should_emit_catalog_steering

        self.assertTrue(
            should_emit_catalog_steering(
                provider="openai",
                depname="gpt-5.4-nano",
                use_responses_api=True,
            )
        )

    def test_should_emit_true_for_legacy(self) -> None:
        from uagent.tools.llm_tool_narrowing import should_emit_catalog_steering

        with mock.patch.dict(os.environ, {"UAGENT_GPT54_TOOL_SEARCH": "legacy"}):
            self.assertTrue(
                should_emit_catalog_steering(
                    provider="openai",
                    depname="gpt-5.4",
                    use_responses_api=True,
                )
            )

    def test_should_emit_true_when_responses_off(self) -> None:
        from uagent.tools.llm_tool_narrowing import should_emit_catalog_steering

        self.assertTrue(
            should_emit_catalog_steering(
                provider="openai",
                depname="gpt-5.4",
                use_responses_api=False,
            )
        )

    def test_strip_catalog_steering_text(self) -> None:
        from uagent.core import _strip_catalog_steering_text

        src = (
            "## Rules\n"
            "- Prefer tools.\n"
            "- If a needed capability is not among the loaded tools, or you are "
            "unsure which tool can do the job, call tool_catalog before answering "
            "or guessing; then tool_load any unloaded tool you need.\n"
            "- Be creative.\n"
        )
        out = _strip_catalog_steering_text(src)
        self.assertNotIn("tool_catalog", out)
        self.assertIn("Prefer tools", out)
        self.assertIn("Be creative", out)

    def test_get_system_prompt_native_omits_catalog(self) -> None:
        from uagent.core import get_system_prompt

        native = get_system_prompt(
            provider="openai",
            depname="gpt-5.4",
            use_responses_api=True,
        )
        self.assertNotIn("tool_catalog", native)

        nano = get_system_prompt(
            provider="openai",
            depname="gpt-5.4-nano",
            use_responses_api=True,
        )
        self.assertIn("tool_catalog", nano)

    def test_build_tools_system_prompt_native_short(self) -> None:
        from uagent.core import build_tools_system_prompt

        specs = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather_wttr",
                    "description": "weather",
                },
            }
        ]
        native = build_tools_system_prompt(
            specs,
            provider="openai",
            depname="gpt-5.4",
            use_responses_api=True,
        )
        self.assertIn("[Available Tools]", native)
        self.assertIn("get_weather_wttr", native)
        self.assertNotIn("tool_catalog", native)

        legacy = build_tools_system_prompt(
            specs,
            provider="openai",
            depname="gpt-5.4",
            use_responses_api=False,
        )
        self.assertIn("tool_catalog", legacy)


if __name__ == "__main__":
    unittest.main()
