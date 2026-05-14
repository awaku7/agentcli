from __future__ import annotations

import os
from pathlib import Path

from typing import Any, Dict, List, Tuple

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
    from ..util_tools import build_initial_messages, image_file_to_data_url

    provider, client, depname = providers.make_client(core)

    messages = build_initial_messages(core=core)
    user_msg: Dict[str, Any] = {"role": "user", "content": user_text}
    messages.append(user_msg)
    try:
        core.log_message(user_msg)
    except Exception:
        pass

    start_idx = len(messages)

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

    def _collect_attachments() -> List[Dict[str, Any]]:
        attachments: List[Dict[str, Any]] = []
        seen: set[str] = set()

        def _add_image_path(raw_path: str) -> None:
            if not raw_path:
                return
            expanded = Path(os.path.expandvars(os.path.expanduser(raw_path)))
            try:
                abs_path = expanded if expanded.is_absolute() else expanded.resolve()
            except Exception:
                abs_path = expanded
            key = str(abs_path)
            if key in seen:
                return
            if not abs_path.exists() or not abs_path.is_file():
                return
            try:
                data_url = image_file_to_data_url(str(abs_path))
            except Exception:
                return
            seen.add(key)
            attachments.append(
                {
                    "type": "image",
                    "mime": "image/png",
                    "name": abs_path.name,
                    "data_url": data_url,
                }
            )

        for msg in messages[start_idx:]:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "tool" or msg.get("name") != "generate_image":
                continue

            for att in msg.get("attachments") or []:
                if not isinstance(att, dict):
                    continue
                if str(att.get("type") or "").lower() != "image":
                    continue
                data_url = att.get("data_url") or att.get("dataUrl") or att.get("data")
                if not isinstance(data_url, str) or not data_url.startswith("data:"):
                    continue
                name = str(att.get("name") or att.get("filename") or "image.png")
                mime = str(att.get("mime") or "image/png")
                key = f"{name}:{mime}:{hash(data_url)}"
                if key in seen:
                    continue
                seen.add(key)
                attachments.append(
                    {"type": "image", "mime": mime, "name": name, "data_url": data_url}
                )
        return attachments

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
                "message": _("No assistant message produced.", default="No assistant message produced."),
            },
        )

    attachments = _collect_attachments()
    if attachments:
        last_assistant = dict(last_assistant)
        last_assistant["attachments"] = attachments
        if not str(last_assistant.get("content") or "").strip():
            last_assistant["content"] = _("Generated image(s).", default="Generated image(s).")

    return last_assistant, None


def run_once(*, user_text: str) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
    mode = _engine_mode()

    if mode == "echo":
        return (
            {"role": "assistant", "content": _("ECHO: %(text)s", default=f"ECHO: {user_text}") % {"text": user_text}},
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
                    "message": _("uagent initialization failed: %(err)s", default=f"uagent initialization failed: {e}") % {"err": e},
                },
            )
        except Exception as e:
            return (
                {"role": "assistant", "content": ""},
                {
                    "code": "INTERNAL",
                    "message": _("uagent execution failed: %(etype)s: %(err)s", default=f"uagent execution failed: {type(e).__name__}: {e}") % {"etype": type(e).__name__, "err": e},
                },
            )

    return (
        {"role": "assistant", "content": ""},
        {
            "code": "FAILED_PRECONDITION",
            "message": _("Unknown UAGENT_A2A_ENGINE: %(mode)s") % {"mode": mode},
        },
    )
