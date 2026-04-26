# -*- coding: utf-8 -*-
"""Lightweight image-session context helpers.

This module keeps the existing single-shot generate_image tool intact and only
adds a small, non-breaking context layer for model names that opt in.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


_GENERATE_IMAGE_TOOL_NAME = "generate_image"


def supports_multi_turn_image(depname: str) -> bool:
    """Enable image-session context only for gpt-5.5 family names."""

    return "gpt-5.5" in (depname or "").strip().lower()


def _tool_call_name(tc: Dict[str, Any]) -> str:
    fn = tc.get("function") or {}
    if isinstance(fn, dict):
        name = fn.get("name")
        if isinstance(name, str):
            return name
    name = tc.get("name")
    return name if isinstance(name, str) else ""


def _tool_call_args(tc: Dict[str, Any]) -> Dict[str, Any]:
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


def _extract_image_paths_from_attachments(attachments: Any) -> List[str]:
    paths: List[str] = []
    for att in attachments or []:
        if not isinstance(att, dict):
            continue
        if str(att.get("type") or "").lower() not in ("image", "image/png", "image/jpeg"):
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


def _extract_image_turns(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    turns: List[Dict[str, Any]] = []
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
                if _tool_call_name(tc) != _GENERATE_IMAGE_TOOL_NAME:
                    continue
                args = _tool_call_args(tc)
                prompt = str(args.get("prompt") or "").strip()
                pending_prompt = prompt or "(prompt unavailable)"
                break

        elif role == "tool" and msg.get("name") == _GENERATE_IMAGE_TOOL_NAME:
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
    messages: List[Dict[str, Any]],
    depname: str,
    *,
    max_turns: int = 3,
) -> Dict[str, Any] | None:
    """Create a small system message that summarizes prior image turns.

    This is only used when the active model name contains gpt-5.5.
    """

    if not supports_multi_turn_image(depname):
        return None

    turns = _extract_image_turns(messages)
    if not turns:
        return None

    recent = turns[-max_turns:]
    lines: List[str] = [
        "Image-session context:",
        "This conversation already generated images.",
        "Use the prior prompts and saved file paths below as context for follow-up edits, variants, or continuations.",
    ]

    for idx, turn in enumerate(recent, start=1):
        lines.append(f"Turn {idx}:")
        lines.append(f"- prompt: {turn['prompt']}")
        paths = turn.get("paths") or []
        for p in paths[:5]:
            lines.append(f"- file: {p}")

    return {
        "role": "system",
        "name": "image_session",
        "content": "\n".join(lines),
    }
