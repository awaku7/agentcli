from __future__ import annotations

import json
import time
from typing import Any, Optional

import requests

from ..env_utils import env_get
from .arg_util import get_bool, get_int, get_str
from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:discord_channel"

DEFAULT_API_BASE = "https://discord.com/api/v10"
DEFAULT_TOKEN_ENV = "DISCORD_BOT_TOKEN"
DEFAULT_TIMEOUT_S = 15
DEFAULT_LIMIT = 10
DEFAULT_WAIT_S = 30
DEFAULT_POLL_INTERVAL_S = 2


def _json_ok(**obj: Any) -> str:
    out: dict[str, Any] = {"ok": True}
    out.update(obj)
    return json.dumps(out, ensure_ascii=False)


def _json_err(message: str, **extra: Any) -> str:
    out: dict[str, Any] = {"ok": False, "error": message}
    out.update(extra)
    return json.dumps(out, ensure_ascii=False)


def _compact_author(msg: dict[str, Any]) -> dict[str, Any]:
    author = msg.get("author") or {}
    return {
        "id": author.get("id"),
        "username": author.get("username"),
        "global_name": author.get("global_name"),
        "bot": author.get("bot"),
    }


def _compact_message(msg: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": msg.get("id"),
        "channel_id": msg.get("channel_id"),
        "content": msg.get("content"),
        "timestamp": msg.get("timestamp"),
        "author": _compact_author(msg),
        "type": msg.get("type"),
        "mention_everyone": msg.get("mention_everyone"),
    }


def _request_json(
    method: str,
    path: str,
    token: str,
    *,
    params: Optional[dict[str, Any]] = None,
    payload: Optional[dict[str, Any]] = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    retries: int = 3,
) -> dict[str, Any]:
    url = DEFAULT_API_BASE.rstrip("/") + path
    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": "uagent-discord-tool/1.0",
        "Accept": "application/json",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"

    last_err: Optional[str] = None
    for attempt in range(retries + 1):
        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=timeout_s,
            )

            if resp.status_code == 429:
                retry_after = 1.0
                try:
                    data = resp.json()
                    retry_after = float(data.get("retry_after") or retry_after)
                except Exception:
                    try:
                        retry_after = float(
                            resp.headers.get("Retry-After", retry_after)
                        )
                    except Exception:
                        retry_after = 1.0
                time.sleep(max(0.2, retry_after) + 0.1)
                continue

            if 200 <= resp.status_code < 300:
                if resp.text.strip():
                    try:
                        return resp.json()
                    except Exception:
                        return {"text": resp.text}
                return {}

            body = resp.text.strip()
            if len(body) > 1000:
                body = body[:1000] + "...(truncated)"
            last_err = f"HTTP {resp.status_code}: {body}"

            if resp.status_code >= 500 and attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            break

        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            break

    raise RuntimeError(last_err or "Discord request failed")


def _get_token(args: dict[str, Any]) -> str:
    token_env = get_str(args, "token_env", DEFAULT_TOKEN_ENV) or DEFAULT_TOKEN_ENV
    token = (env_get(token_env) or "").strip()
    if not token:
        raise ValueError(f"Environment variable {token_env!r} is not set")
    return token


def _get_self_user_id(token: str) -> str:
    me = _request_json("GET", "/users/@me", token)
    user_id = str(me.get("id") or "")
    if not user_id:
        raise RuntimeError("Failed to resolve bot user id")
    return user_id


def _fetch_recent_messages(
    token: str,
    channel_id: str,
    *,
    limit: int,
    after: Optional[str] = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": max(1, min(100, int(limit)))}
    if after:
        params["after"] = after
    data = _request_json(
        "GET", f"/channels/{channel_id}/messages", token, params=params
    )
    if not isinstance(data, list):
        raise RuntimeError("Unexpected response when fetching channel messages")
    return data


TOOL_SPEC: dict[str, Any] = {
    "load_order": 10000,
    "tool_level": 1,
    "tool_genre": "comm",
    "type": "function",
    "function": {
        "name": "discord_channel_chat",
        "description": _(
            "tool.description",
            default=(
                "Interact with a specific Discord channel using a bot token: send messages, "
                "read recent messages, and optionally wait for replies after sending."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "discord_channel",
                "discord channel",
            ],
        ),
        "x_search_terms_en": [
            "discord_channel",
            "discord channel",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": _(
                        "param.action.description",
                        default="Action: send / send_and_wait / history",
                    ),
                },
                "channel_id": {
                    "type": "string",
                    "description": _(
                        "param.channel_id.description",
                        default="Target Discord channel ID.",
                    ),
                },
                "message": {
                    "type": "string",
                    "description": _(
                        "param.message.description",
                        default="Message.",
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": _(
                        "param.limit.description",
                        default="Number of messages to fetch for history/replies.",
                    ),
                    "default": DEFAULT_LIMIT,
                },
                "wait_s": {
                    "type": "integer",
                    "description": _(
                        "param.wait_s.description",
                        default="How long to wait for replies after sending (seconds).",
                    ),
                    "default": DEFAULT_WAIT_S,
                },
                "poll_interval_s": {
                    "type": "integer",
                    "description": _(
                        "param.poll_interval_s.description",
                        default="Polling interval while waiting for replies (seconds).",
                    ),
                    "default": DEFAULT_POLL_INTERVAL_S,
                },
                "token_env": {
                    "type": "string",
                    "description": _(
                        "param.token_env.description",
                        default="Environment variable name that stores the Discord bot token.",
                    ),
                    "default": DEFAULT_TOKEN_ENV,
                },
                "exclude_bots": {
                    "type": "boolean",
                    "description": _(
                        "param.exclude_bots.description",
                        default="When waiting, ignore bot messages.",
                    ),
                    "default": True,
                },
            },
            "required": ["action", "channel_id"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    cb = get_callbacks()
    if cb.set_status:
        cb.set_status(True, STATUS_LABEL)
    try:
        action = get_str(args, "action", "").lower()
        channel_id = get_str(args, "channel_id", "")
        if not action:
            return _json_err(_("err.missing_action", default="Missing 'action'."))
        if not channel_id:
            return _json_err(
                _("err.missing_channel_id", default="Missing 'channel_id'.")
            )

        token = _get_token(args)

        if action == "history":
            limit = get_int(args, "limit", DEFAULT_LIMIT)
            messages = _fetch_recent_messages(token, channel_id, limit=limit)
            return _json_ok(
                action=action,
                channel_id=channel_id,
                messages=[_compact_message(m) for m in messages],
            )

        if action not in ("send", "send_and_wait"):
            return _json_err(
                _("err.invalid_action", default="Invalid action: {action}").format(
                    action=action
                )
            )

        message = get_str(args, "message", "")
        if not message:
            return _json_err(_("err.missing_message", default="Missing 'message'."))
        if len(message) > 2000:
            return _json_err(
                _(
                    "err.message_too_long",
                    default="Discord message content must be 2000 characters or less.",
                ),
                length=len(message),
                max_length=2000,
            )

        sent = _request_json(
            "POST",
            f"/channels/{channel_id}/messages",
            token,
            payload={"content": message},
        )

        if action == "send":
            return _json_ok(
                action=action,
                channel_id=channel_id,
                sent_message=_compact_message(sent),
            )

        wait_s = max(0, get_int(args, "wait_s", DEFAULT_WAIT_S))
        poll_interval_s = max(
            1, get_int(args, "poll_interval_s", DEFAULT_POLL_INTERVAL_S)
        )
        exclude_bots = get_bool(args, "exclude_bots", True)
        limit = max(1, min(100, get_int(args, "limit", DEFAULT_LIMIT)))

        if wait_s == 0:
            return _json_ok(
                action=action,
                channel_id=channel_id,
                sent_message=_compact_message(sent),
                replies=[],
                timed_out=True,
                waited_s=0,
            )

        self_user_id = _get_self_user_id(token)
        sent_id = str(sent.get("id") or "")
        start = time.time()
        seen_ids: set[str] = set()
        replies: list[dict[str, Any]] = []

        while True:
            elapsed = time.time() - start
            if elapsed >= wait_s:
                break

            msgs = _fetch_recent_messages(
                token,
                channel_id,
                limit=max(1, min(100, limit)),
                after=sent_id,
            )

            for msg in reversed(msgs):
                msg_id = str(msg.get("id") or "")
                if not msg_id or msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)

                author = msg.get("author") or {}
                if exclude_bots and bool(author.get("bot")):
                    continue
                if str(author.get("id") or "") == self_user_id:
                    continue
                replies.append(_compact_message(msg))

            if replies:
                break

            time.sleep(min(float(poll_interval_s), max(0.5, wait_s - elapsed)))

        return _json_ok(
            action=action,
            channel_id=channel_id,
            sent_message=_compact_message(sent),
            replies=replies,
            timed_out=not bool(replies),
            waited_s=round(time.time() - start, 3),
        )

    except Exception as e:
        return _json_err(
            _("err.exception", default="Exception"),
            exception=type(e).__name__,
            detail=str(e),
        )
    finally:
        if cb.set_status:
            cb.set_status(False, STATUS_LABEL)
