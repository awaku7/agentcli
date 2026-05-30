# -*- coding: utf-8 -*-
"""Lightweight image-session context helpers.

This module keeps the existing single-shot generate_image tool intact and only
adds a small, non-breaking context layer for model names that opt in.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .i18n import _

_GENERATE_IMAGE_TOOL_NAME = "generate_image"
_SCREENSHOT_TOOL_NAME = "screenshot"


def supports_multi_turn_image(depname: str) -> bool:
    """Enable image-session context for gpt-5 family names."""

    dn = (depname or "").strip().lower()
    return dn.startswith("gpt-5")


def _tool_call_name(tc: dict[str, Any]) -> str:
    fn = tc.get("function") or {}
    if isinstance(fn, dict):
        name = fn.get("name")
        if isinstance(name, str):
            return name
    name = tc.get("name")
    return name if isinstance(name, str) else ""


def _tool_call_args(tc: dict[str, Any]) -> dict[str, Any]:
    payload = (tc.get("function") or {}).get("arguments")
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str) and payload.strip():
        try:
            obj = json.loads(payload)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _extract_image_paths_from_attachments(attachments: Any) -> list[str]:
    paths: list[str] = []
    for att in attachments or []:
        if not isinstance(att, dict):
            continue
        if str(att.get("type") or "").lower() not in (
            "image",
            "image/png",
            "image/jpeg",
        ):
            continue
        candidate = (
            att.get("saved_path")
            or att.get("path")
            or att.get("file_path")
            or att.get("filename")
            or att.get("name")
        )
        if isinstance(candidate, str):
            candidate = candidate.strip()
            if candidate and candidate not in paths:
                paths.append(candidate)
    return paths


def _extract_image_turns(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    pending_prompt: Optional[str] = None

    for msg in messages or []:
        if not isinstance(msg, dict):
            continue

        role = msg.get("role")
        if role == "assistant":
            tool_calls = msg.get("tool_calls")
            if not isinstance(tool_calls, list):
                pending_prompt = None
                continue

            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                tool_name = _tool_call_name(tc)
                if tool_name not in (
                    _GENERATE_IMAGE_TOOL_NAME,
                    _SCREENSHOT_TOOL_NAME,
                ):
                    continue
                args = _tool_call_args(tc)
                if tool_name == _GENERATE_IMAGE_TOOL_NAME:
                    prompt = str(args.get("prompt") or "").strip()
                    pending_prompt = prompt or _("(prompt unavailable)")
                else:
                    window_title = str(args.get("window_title") or "").strip()
                    pending_prompt = (
                        _("screenshot: %(title)s") % {"title": window_title}
                        if window_title
                        else _("screenshot")
                    )
                break

        elif role == "tool" and msg.get("name") in (
            _GENERATE_IMAGE_TOOL_NAME,
            _SCREENSHOT_TOOL_NAME,
        ):
            paths = _extract_image_paths_from_attachments(msg.get("attachments"))
            if pending_prompt or paths:
                turns.append(
                    {
                        "prompt": pending_prompt or "(prompt unavailable)",
                        "paths": paths,
                    }
                )
            pending_prompt = None

    return turns


def build_image_session_message(
    messages: list[dict[str, Any]],
    depname: str,
    *,
    max_turns: int = 3,
) -> dict[str, Any] | None:
    """Create a small system message that summarizes prior image turns.

    This is only used when the active model name contains gpt-5.
    """

    if not supports_multi_turn_image(depname):
        return None

    turns = _extract_image_turns(messages)
    if not turns:
        return None

    recent = turns[-max_turns:]
    lines: list[str] = [
        _("Image-session context:"),
        _("This conversation already generated images."),
        _(
            "Use the prior prompts and saved file paths below as context for follow-up edits, variants, or continuations."
        ),
    ]

    for idx, turn in enumerate(recent, start=1):
        lines.append(_("Turn %(idx)d:") % {"idx": idx})
        lines.append(_("- prompt: %(prompt)s") % {"prompt": turn["prompt"]})
        paths = turn.get("paths") or []
        for p in paths[:5]:
            lines.append(_("- file: %(path)s") % {"path": p})

    return {
        "role": "system",
        "name": "image_session",
        "content": "\n".join(lines),
    }
