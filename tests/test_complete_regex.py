import sys

from uagent.uagent_llm import _completion_regex_matches as round_completion_matches
from uagent.util_cmd_auto import _completion_regex_matches as auto_completion_matches
from uagent.util_common import parse_startup_args


def test_parse_complete_regex_flag(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["uag", "--inject-message", "work", "--complete-regex", "^ALL DONE$"],
    )

    args, unknown = parse_startup_args()

    assert args["complete_regex"] == "^ALL DONE$"
    assert unknown == []


def test_round_completion_regex_matches_multiline_text():
    assert round_completion_matches("progress\nALL DONE\n", r"^ALL DONE$")
    assert not round_completion_matches("progress", r"^ALL DONE$")


def test_auto_completion_regex_uses_latest_assistant_message():
    messages = [
        {"role": "assistant", "content": "old result"},
        {"role": "user", "content": "continue"},
        {"role": "assistant", "content": "ALL DONE"},
    ]

    assert auto_completion_matches(messages, r"^ALL DONE$")
    assert not auto_completion_matches(messages, r"^FAILED$")
