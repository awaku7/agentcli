from __future__ import annotations

import json

from uagent.utils.secret_mask import (
    SECRET_MASK,
    looks_like_password_field,
    looks_like_secret_key,
    mask_args,
    mask_message,
    mask_tool_call_arguments_json,
)


def test_looks_like_secret_key_basic():
    assert looks_like_secret_key("password")
    assert looks_like_secret_key("api_key")
    assert looks_like_secret_key("accessToken")
    assert not looks_like_secret_key("is_password")
    assert not looks_like_secret_key("username")


def test_looks_like_password_field_selector():
    assert looks_like_password_field('[data-testid="loginPasswordInput"]')
    assert looks_like_password_field("input[type=password]")
    assert looks_like_password_field("#password")
    assert not looks_like_password_field('[data-testid="loginUsernameInput"]')


def test_mask_args_password_key():
    masked = mask_args({"password": "secret123", "user": "alice"})
    assert masked["password"] == SECRET_MASK
    assert masked["user"] == "alice"


def test_mask_args_browser_fill_password_selector():
    args = {
        "session_id": "bp_test",
        "session_action": "act",
        "actions": [
            {
                "type": "fill",
                "selector": '[data-testid="loginUsernameInput"]',
                "value": "ukawa.bsky.social",
            },
            {
                "type": "fill",
                "selector": '[data-testid="loginPasswordInput"]',
                "value": "super-secret-password",
            },
            {
                "type": "keyboard_type",
                "selector": "input[type=password]",
                "value": "another-secret",
            },
            {"type": "click", "selector": "button"},
        ],
    }
    masked = mask_args(args)
    assert masked["actions"][0]["value"] == "ukawa.bsky.social"
    assert masked["actions"][1]["value"] == SECRET_MASK
    assert masked["actions"][2]["value"] == SECRET_MASK
    assert masked["actions"][3]["type"] == "click"
    # session_id / session_action should remain (not over-masked)
    assert masked["session_id"] == "bp_test"
    assert masked["session_action"] == "act"


def test_mask_tool_call_arguments_json():
    raw = json.dumps(
        {
            "actions": [
                {
                    "type": "fill",
                    "selector": '[data-testid="loginPasswordInput"]',
                    "value": "plain-password",
                }
            ]
        },
        ensure_ascii=False,
    )
    masked = mask_tool_call_arguments_json(raw)
    parsed = json.loads(masked)
    assert parsed["actions"][0]["value"] == SECRET_MASK
    assert "plain-password" not in masked


def test_mask_message_tool_calls():
    msg = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "browser_playwright",
                    "arguments": json.dumps(
                        {
                            "actions": [
                                {
                                    "type": "fill",
                                    "selector": '[data-testid="loginPasswordInput"]',
                                    "value": "kq767efebsky",
                                }
                            ]
                        }
                    ),
                },
            }
        ],
    }
    masked = mask_message(msg)
    args = masked["tool_calls"][0]["function"]["arguments"]
    assert "kq767efebsky" not in args
    assert SECRET_MASK in args


def test_mask_message_human_ask_secret():
    content = json.dumps(
        {
            "tool": "human_ask",
            "display_reply": "[SECRET]",
            "user_reply": "my-password",
        }
    )
    masked = mask_message({"role": "tool", "content": content})
    parsed = json.loads(masked["content"])
    assert parsed["user_reply"] == SECRET_MASK
