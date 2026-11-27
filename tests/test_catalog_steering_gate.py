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

    def test_gemini_interactions_retrieval_omits_catalog_guidance(self) -> None:
        from uagent.core import build_tools_system_prompt, get_system_prompt

        with (
            mock.patch.dict(
                os.environ,
                {"UAGENT_GEMINI_API_MODE": "", "UAGENT_EMBEDDED": "0"},
            ),
            mock.patch(
                "uagent.llmcapa_util.supports_feature",
                side_effect=lambda feature, *_args, default=None: (
                    True if feature in {"interactions_api", "tool_search"} else default
                ),
            ),
        ):
            system_prompt = get_system_prompt(
                provider="gemini",
                depname="gemini-3.8-flash",
                use_responses_api=False,
            )
            tools_prompt = build_tools_system_prompt(
                [
                    {
                        "type": "function",
                        "function": {"name": "lookup", "description": "Look up."},
                    }
                ],
                provider="gemini",
                depname="gemini-3.8-flash",
                use_responses_api=False,
            )

        self.assertNotIn("tool_catalog", system_prompt)
        self.assertNotIn("tool_catalog", tools_prompt)

    def test_native_responses_registry_omits_management_tools_on_every_round(
        self,
    ) -> None:
        from uagent.runtime.tool_discovery import (
            ToolDiscoveryDecision,
            ToolDiscoveryMode,
        )
        from uagent.uagent_llm import _select_registry_tool_specs

        specs = [
            {"type": "function", "function": {"name": name}}
            for name in (
                "ordinary_tool",
                "tool_catalog",
                "tool_load",
                "unload_tool",
            )
        ]
        native = ToolDiscoveryDecision(ToolDiscoveryMode.NATIVE_SEARCH, "test")

        for round_count in (1, 2):
            with self.subTest(round_count=round_count):
                selected = _select_registry_tool_specs(
                    specs,
                    discovery=native,
                    use_responses_api=True,
                    round_count=round_count,
                )
                self.assertEqual(
                    [spec["function"]["name"] for spec in selected],
                    ["ordinary_tool"],
                )

    def test_legacy_bootstrap_keeps_management_tools(self) -> None:
        from uagent.runtime.tool_discovery import (
            ToolDiscoveryDecision,
            ToolDiscoveryMode,
        )
        from uagent.uagent_llm import _select_registry_tool_specs

        specs = [
            {"type": "function", "function": {"name": name}}
            for name in (
                "ordinary_tool",
                "tool_catalog",
                "tool_load",
                "unload_tool",
            )
        ]
        legacy = ToolDiscoveryDecision(ToolDiscoveryMode.LEGACY_CATALOG, "test")

        selected = _select_registry_tool_specs(
            specs,
            discovery=legacy,
            use_responses_api=True,
            round_count=1,
        )
        self.assertEqual(
            [spec["function"]["name"] for spec in selected],
            ["tool_catalog", "tool_load", "unload_tool"],
        )


if __name__ == "__main__":
    unittest.main()
