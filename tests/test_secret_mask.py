from __future__ import annotations

import json

from uagent.utils.secret_mask import (
    SECRET_MASK,
    _mask_inline_secrets,
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


def test_inline_secret_mask_covers_bearer_cookie_and_camel_case_keys():
    raw = (
        "Authorization: Bearer bearer-dummy; "
        "accessToken=camel-dummy; Cookie: session=dummy-cookie\n"
        "Authorization: Basic basic-dummy"
    )

    masked = _mask_inline_secrets(raw)

    assert "bearer-dummy" not in masked
    assert "camel-dummy" not in masked
    assert "dummy-cookie" not in masked
    assert "basic-dummy" not in masked
    assert SECRET_MASK in masked


def test_authorization_prose_keeps_remainder_but_header_credentials_are_masked():
    prose = "Authorization: required; visit https://example/approve"
    spaced_prose = "Authorization: required ; visit https://example/approve?next=home"
    bearer_prose = '"Bearer authentication is common"'
    long_bearer_prose = "Bearer responsibilities are assigned here"
    basic_prose = "Authorization: Basic authentication is described here"
    raw_header_prose = "Authorization: responsibilities are assigned here"
    header = "Authorization: Bearer bearer-header-dummy; keep this note"
    basic_header = "Authorization: Basic basic-dummy"
    alpha_basic_header = "Authorization: Basic YTphYWFh"
    alpha_bearer_header = "Authorization: Bearer alphabeticbearertoken"
    crlf_header = "Authorization: Basic YTphYWFh\r\nHost: example"
    opaque_header = (
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature"
    )

    assert _mask_inline_secrets(prose) == prose
    assert _mask_inline_secrets(spaced_prose) == spaced_prose
    assert _mask_inline_secrets(bearer_prose) == bearer_prose
    assert _mask_inline_secrets(long_bearer_prose) == long_bearer_prose
    assert _mask_inline_secrets(basic_prose) == basic_prose
    assert _mask_inline_secrets(raw_header_prose) == raw_header_prose
    assert _mask_inline_secrets(header) == (
        "Authorization: Bearer ********; keep this note"
    )
    assert _mask_inline_secrets(basic_header) == "Authorization: Basic ********"
    assert _mask_inline_secrets(alpha_basic_header) == "Authorization: Basic ********"
    assert _mask_inline_secrets(alpha_bearer_header) == (
        "Authorization: Bearer ********"
    )
    assert _mask_inline_secrets(crlf_header) == (
        "Authorization: Basic ********\r\nHost: example"
    )
    assert "eyJhbGciOiJIUzI1NiJ9" not in _mask_inline_secrets(opaque_header)
    assert SECRET_MASK in _mask_inline_secrets(opaque_header)


def test_authorization_unknown_schemes_and_short_bearers_are_masked_without_prose_loss():
    assert _mask_inline_secrets("Authorization: ApiKey abc123") == (
        "Authorization: ApiKey ********"
    )
    assert _mask_inline_secrets("Authorization: ApiKey abcdef") == (
        "Authorization: ApiKey ********"
    )
    assert _mask_inline_secrets("Authorization: permission needed") == (
        "Authorization: permission needed"
    )
    assert (
        _mask_inline_secrets('Authorization: Digest username="Mufasa", realm="test"')
        == "Authorization: Digest ********"
    )
    assert _mask_inline_secrets("Bearer abc123") == "Bearer ********"
    assert _mask_inline_secrets("Bearer abcdefghijklmnopqrstuvwxyz") == (
        "Bearer ********"
    )
    quoted_prose = '"Bearer authentication is common"'
    assert _mask_inline_secrets(quoted_prose) == quoted_prose


def test_quoted_inline_secret_is_masked_as_a_whole_value():
    assert _mask_inline_secrets("password: 'correct horse battery staple'") == (
        "password: '********'"
    )


def test_namespaced_environment_secret_assignments_are_masked():
    raw = (
        "OPENAI_API_KEY=openai-key-dummy "
        "AWS_SECRET_ACCESS_KEY=aws-secret-dummy "
        "UAGENT_AUTH_TOKEN=uagent-token-dummy"
    )

    masked = _mask_inline_secrets(raw)

    assert "OPENAI_API_KEY=********" in masked
    assert "AWS_SECRET_ACCESS_KEY=********" in masked
    assert "UAGENT_AUTH_TOKEN=********" in masked
    assert "openai-key-dummy" not in masked
    assert "aws-secret-dummy" not in masked
    assert "uagent-token-dummy" not in masked
