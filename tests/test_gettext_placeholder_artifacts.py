import gettext
import re
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "locales"
ARTIFACT_RE = re.compile(r"(?:PH_|___[0-9]|__[0-9])")
ARTIFACT_BYTES_RE = re.compile(rb"(?:PH_|___[0-9]|__[0-9])")
AUTO_REVIEW_ARTIFACT_RE = re.compile(r"\b[\w]*_[0-9]+\b")
AUTO_REVIEW_FORMAT_RE = re.compile(r"CONTINUE:\s*<[^>\n]+>")
AUTO_REVIEW_MSGID = "auto.review_judgment_system_prompt"

MULTILINE_MSGIDS = {
    "auto_review": "auto.review_judgment_system_prompt",
    "warning": (
        "[WARN] LLM returned an empty assistant message without tool calls.\n"
        "provider=%(provider)s depname=%(depname)s "
        "empty_no_tool_rounds=%(empty_no_tool_rounds)s "
        "(max=%(empty_no_tool_max)s)\n"
        "This may happen with some providers (including Grok/xAI and "
        "OpenAI-compatible endpoints) after tool calls. You can try setting "
        "UAGENT_EMPTY_NO_TOOL_MAX to a higher value, or switching provider."
    ),
    "tool_calling": (
        "[Tool calling rules]\n"
        "        - When calling a tool/function, you MUST provide "
        "function_call.arguments as a JSON object.\n"
        "        - The JSON object MUST include all required parameters defined "
        "by the tool schema.\n"
        "        - Never call a tool with an empty object {} unless the tool has "
        "no required parameters.\n"
        "        - If you do not have a required parameter, ask the user for it "
        "using human_ask instead of guessing.\n"
        "        "
    ),
    "skills_help": (
        "Built-in: list/active/clear (see runtime skills handlers).\n"
        ":skills list <keyword>  Filter skills by keyword (name/description).\n"
        ":skills find <keyword>  Same as list with filter.\n"
        "Dynamic subcommands come from tool CMD_SPEC "
        "(install, uninstall, apm, mp_search).\n"
        "Use :help skills install for a subcommand."
    ),
    "tools_help": (
        ":tools on|off           Enable/disable sending tools to the LLM\n"
        ":tools on|off <genre>   Enable/disable a tool genre "
        "(and sync global on)\n"
        ":tools list [query]     List loaded tools\n"
        ":tools load <name>      Load one tool by name\n"
        ":tools reload           Reload tool modules from disk\n"
        ":tools output           Toggle showing tool results in UI"
    ),
}

REPAIRED_MULTILINE_LOCALES = {
    "cs": ("auto_review", "tools_help"),
    "da": ("auto_review", "tool_calling"),
    "el": ("warning",),
    "fi": ("auto_review", "skills_help", "tools_help"),
    "fil": ("tool_calling", "tools_help"),
    "he": ("tools_help",),
    "hu": ("auto_review", "skills_help", "tools_help"),
    "mn": ("warning", "auto_review", "skills_help", "tools_help"),
    "ms": ("tool_calling",),
    "nn": ("auto_review", "skills_help", "tools_help"),
    "ro": ("warning", "tools_help"),
    "sv": ("skills_help", "tools_help"),
    "sw": ("skills_help", "tools_help"),
}


def test_gettext_catalogs_do_not_ship_placeholder_artifacts():
    offenders = []

    for path in sorted(LOCALES_DIR.glob("*/LC_MESSAGES/uag.po")):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if ARTIFACT_RE.search(line):
                offenders.append(
                    f"{path.relative_to(LOCALES_DIR)}:{line_number}: {line.strip()}"
                )

    for path in sorted(LOCALES_DIR.glob("*/LC_MESSAGES/uag.mo")):
        if ARTIFACT_BYTES_RE.search(path.read_bytes()):
            offenders.append(
                f"{path.relative_to(LOCALES_DIR)}: binary contains placeholder artifact"
            )

    message = "Placeholder artifacts remain in gettext catalogs:\n" + "\n".join(
        offenders
    )
    assert not offenders, message


def test_repaired_multiline_gettext_entries_use_real_newlines():
    offenders = []

    for locale, keys in REPAIRED_MULTILINE_LOCALES.items():
        catalog = LOCALES_DIR / locale / "LC_MESSAGES" / "uag.mo"
        with catalog.open("rb") as stream:
            translation = gettext.GNUTranslations(stream)

        for key in keys:
            msgid = MULTILINE_MSGIDS[key]
            translated = translation.gettext(msgid)
            if translated == msgid:
                offenders.append(f"{locale}:{key}: untranslated")
                continue
            if "\n" not in translated:
                offenders.append(f"{locale}:{key}: missing real newline")
            if "\\n" in translated:
                offenders.append(f"{locale}:{key}: contains literal backslash-n")
            if key == "auto_review" and "CONTINUE: <reason>" not in translated:
                offenders.append(
                    f"{locale}:{key}: missing CONTINUE: <reason> protocol format"
                )

    message = "Broken multiline gettext entries:\n" + "\n".join(offenders)
    assert not offenders, message



def test_all_non_english_auto_review_prompts_are_structurally_complete():
    offenders = []

    for catalog in sorted(LOCALES_DIR.glob("*/LC_MESSAGES/uag.mo")):
        locale = catalog.parent.parent.name
        if locale == "en":
            continue

        with catalog.open("rb") as stream:
            translation = gettext.GNUTranslations(stream)

        translated = translation.gettext(AUTO_REVIEW_MSGID)
        if translated == AUTO_REVIEW_MSGID:
            offenders.append(f"{locale}: untranslated")
            continue

        if translated.count("\n") < 5:
            offenders.append(f"{locale}: expected six-line prompt")
        for token in ("%(goal)s", "COMPLETE", "CONTINUE"):
            if token not in translated:
                offenders.append(f"{locale}: missing {token}")
        if "\\n" in translated:
            offenders.append(f"{locale}: contains literal backslash-n")
        if AUTO_REVIEW_ARTIFACT_RE.search(translated):
            offenders.append(f"{locale}: contains underscore-number artifact")
        if not AUTO_REVIEW_FORMAT_RE.search(translated):
            offenders.append(f"{locale}: missing CONTINUE format")

    message = "Broken auto-review gettext prompts:\n" + "\n".join(offenders)
    assert not offenders, message
