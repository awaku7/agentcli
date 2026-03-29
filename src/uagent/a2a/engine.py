from __future__ import annotations

from typing import Any, Dict, Tuple

from ..env_utils import env_get
from ..i18n import _


def _norm(v: str) -> str:
    return (v or "").strip().lower()


def _engine_mode() -> str:
    # Default: run the real uagent LLM flow.
    # Tests can set UAGENT_A2A_ENGINE=echo.
    return _norm(env_get("UAGENT_A2A_ENGINE", "uag")) or "uag"


def run_once_uag(*, user_text: str) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
    """Run one uagent round-trip and return (assistant_message, error)."""

    # Local imports to avoid import-time side effects unless A2A server is used.
    from .. import core as core
    from .. import uagent_llm as llm_util
    from .. import util_providers as providers
    from .. import util_tools as tools_util
    from ..util_tools import build_initial_messages

    provider, client, depname = providers.make_client(core)

    messages = build_initial_messages(core=core)
    user_msg: Dict[str, Any] = {"role": "user", "content": user_text}
    messages.append(user_msg)
    try:
        core.log_message(user_msg)
    except Exception:
        pass

    # Execute one round (same as CLI/web usage)
    llm_util.run_llm_rounds(
        provider,
        client,
        depname,
        messages,
        core=core,
        make_client_fn=providers.make_client,
        append_result_to_outfile_fn=tools_util.append_result_to_outfile,
        try_open_images_from_text_fn=tools_util.try_open_images_from_text,
    )

    # Find last assistant message
    last_assistant: Dict[str, Any] | None = None
    for m in reversed(messages):
        if m.get("role") == "assistant":
            last_assistant = m
            break

    if not last_assistant:
        return (
            {"role": "assistant", "content": ""},
            {
                "code": "INTERNAL",
                "message": "No assistant message produced.",
            },
        )

    return last_assistant, None


def run_once(*, user_text: str) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
    mode = _engine_mode()

    if mode == "echo":
        return (
            {"role": "assistant", "content": f"ECHO: {user_text}"},
            None,
        )

    if mode in ("uag", "uagent"):
        try:
            return run_once_uag(user_text=user_text)
        except SystemExit as e:
            return (
                {"role": "assistant", "content": ""},
                {
                    "code": "FAILED_PRECONDITION",
                    "message": f"uagent initialization failed: {e}",
                },
            )
        except Exception as e:
            return (
                {"role": "assistant", "content": ""},
                {
                    "code": "INTERNAL",
                    "message": f"uagent execution failed: {type(e).__name__}: {e}",
                },
            )

    return (
        {"role": "assistant", "content": ""},
        {
            "code": "FAILED_PRECONDITION",
            "message": _("Unknown UAGENT_A2A_ENGINE: %(mode)s") % {"mode": mode},
        },
    )
