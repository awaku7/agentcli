from __future__ import annotations

from typing import Any


def apply_deepseek_responses_compat(
    resp_kwargs: dict[str, Any],
    *,
    provider: str,
    depname: str,
) -> None:
    """Apply DeepSeek Responses API compatibility workarounds.

    Mutates resp_kwargs in-place.

    DeepSeek Responses API (https://api.deepseek.com/responses):
      - Stateless: ``previous_response_id`` is not supported (handled by caller).
      - Only ``deepseek-v4-flash`` is supported so far.
      - ``context_management`` (OpenAI compaction) is not a supported parameter.
      - ``text.verbosity`` is not a supported parameter.
      - ``reasoning.effort`` accepts the full OpenAI range; the server maps
        minimal/low -> low, medium/high/xhigh -> high, max -> max.
    """

    if provider != "deepseek":
        return

    # OpenAI Responses API compaction is not supported by DeepSeek.
    resp_kwargs.pop("context_management", None)

    # DeepSeek only supports the text output config; drop verbosity.
    text_cfg = resp_kwargs.get("text")
    if isinstance(text_cfg, dict):
        text_cfg.pop("verbosity", None)
        if not text_cfg:
            resp_kwargs.pop("text", None)
