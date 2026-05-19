from __future__ import annotations

import json
from typing import Any, Dict

import requests

from ..env_utils import env_get
from .arg_util import get_str
from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:teams_webhook"

DEFAULT_WEBHOOK_ENV = "TEAMS_WEBHOOK"
DEFAULT_TIMEOUT_S = 15


def _json_ok(**obj: Any) -> str:
    out: Dict[str, Any] = {"ok": True}
    out.update(obj)
    return json.dumps(out, ensure_ascii=False)


def _json_err(message: str, **extra: Any) -> str:
    out: Dict[str, Any] = {"ok": False, "error": message}
    out.update(extra)
    return json.dumps(out, ensure_ascii=False)


def _get_webhook_url(args: Dict[str, Any]) -> str:
    env_name = get_str(args, "webhook_env", DEFAULT_WEBHOOK_ENV) or DEFAULT_WEBHOOK_ENV
    url = (env_get(env_name) or "").strip()
    if not url:
        raise ValueError(f"Environment variable {env_name!r} is not set")
    return url


def _parse_json_arg(value: Any, field_name: str) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        return json.loads(value)
    raise TypeError(f"{field_name} must be a JSON string or object")


def _build_payload(args: Dict[str, Any]) -> Dict[str, Any]:
    raw_payload = args.get("payload_json")
    if raw_payload not in (None, ""):
        payload = _parse_json_arg(raw_payload, "payload_json")
        if not isinstance(payload, dict):
            raise ValueError("payload_json must decode to an object")
        return payload

    message = get_str(args, "message", "")
    title = get_str(args, "title", "")
    summary = get_str(args, "summary", "")
    image_url = get_str(args, "image_url", "")
    theme_color = get_str(args, "theme_color", "")

    if image_url or title or summary or theme_color:
        card: Dict[str, Any] = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
        }
        if summary:
            card["summary"] = summary
        elif message:
            card["summary"] = message
        if title:
            card["title"] = title
        if message:
            card["text"] = message
        if theme_color:
            card["themeColor"] = theme_color
        if image_url:
            card["sections"] = [
                {
                    "images": [{"image": image_url}],
                }
            ]
        return card

    return {"text": message}


def _post_message(
    url: str, payload: Dict[str, Any], timeout_s: int = DEFAULT_TIMEOUT_S
) -> Dict[str, Any]:
    resp = requests.post(
        url,
        json=payload,
        timeout=timeout_s,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
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
    raise RuntimeError(f"HTTP {resp.status_code}: {body}")


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "teams_webhook_post",
        "description": _(
            "tool.description",
            default="Post a message or webhook-supported JSON payload to a Microsoft Teams Incoming Webhook URL stored in an environment variable.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="Post a payload to Microsoft Teams Incoming Webhook. Return JSON only.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "teams_webhook",
                "teams webhook",
                "post message",
                "incoming webhook",
                "notify teams",
            ],
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": _(
                        "param.message.description",
                        default="Message text to post to Teams. Used as plain text unless card fields are provided.",
                    ),
                },
                "title": {
                    "type": "string",
                    "description": _(
                        "param.title.description",
                        default="Card title for webhook-supported payloads.",
                    ),
                },
                "summary": {
                    "type": "string",
                    "description": _(
                        "param.summary.description",
                        default="Card summary for webhook-supported payloads.",
                    ),
                },
                "image_url": {
                    "type": "string",
                    "description": _(
                        "param.image_url.description",
                        default="Image URL for webhook-supported payloads.",
                    ),
                },
                "theme_color": {
                    "type": "string",
                    "description": _(
                        "param.theme_color.description",
                        default="Card theme color as a hex string without #.",
                    ),
                },
                "payload_json": {
                    "type": ["string", "object"],
                    "description": _(
                        "param.payload_json.description",
                        default="Raw webhook payload as JSON string or object. If provided, it is sent as-is.",
                    ),
                },
                "webhook_env": {
                    "type": "string",
                    "description": _(
                        "param.webhook_env.description",
                        default="Environment variable name that stores the Teams webhook URL.",
                    ),
                    "default": DEFAULT_WEBHOOK_ENV,
                },
                "timeout_s": {
                    "type": "integer",
                    "description": _(
                        "param.timeout_s.description",
                        default="Request timeout in seconds.",
                    ),
                    "default": DEFAULT_TIMEOUT_S,
                },
            },
            "required": ["message"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()
    if cb.set_status:
        cb.set_status(True, STATUS_LABEL)
    try:
        message = get_str(args, "message", "")
        payload_json = args.get("payload_json")
        if not message and payload_json in (None, ""):
            return _json_err(_("err.missing_message", default="Missing 'message'."))

        timeout_s = int(args.get("timeout_s") or DEFAULT_TIMEOUT_S)
        if timeout_s <= 0:
            timeout_s = DEFAULT_TIMEOUT_S

        webhook_url = _get_webhook_url(args)
        payload = _build_payload(args)
        result = _post_message(webhook_url, payload, timeout_s=timeout_s)
        return _json_ok(posted=True, payload=payload, result=result)

    except Exception as e:
        return _json_err(
            _("err.exception", default="Exception"),
            exception=type(e).__name__,
            detail=str(e),
        )
    finally:
        if cb.set_status:
            cb.set_status(False, STATUS_LABEL)
