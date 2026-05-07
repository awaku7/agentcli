from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from uag_envsec.secret_core import decrypt_text, encrypt_text, ensure_key_file

from .env_validate import format_missing_env_message, validate_startup_env
from .i18n import _


def _format_env_value(value: str) -> str:
    if value == "":
        return '""'
    if "\n" in value or "\r" in value:
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )
        return f'"{escaped}"'
    if re.fullmatch(r"[A-Za-z0-9_./:@%+=,-]+", value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _build_uagent_env_text(prefix: str = "UAGENT_") -> str:
    keys = sorted(k for k in os.environ if k.startswith(prefix))
    if not keys:
        return ""
    lines = [f"{key}={_format_env_value(os.environ.get(key, ''))}" for key in keys]
    return "\n".join(lines).rstrip() + "\n"


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8", newline="\n")
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _read_envsec_plaintext(sec_path: Path) -> str:
    body = sec_path.read_text(encoding="utf-8").strip()
    if not body:
        return ""
    local_key = Path.cwd() / ".uagent.key"
    kp = str(local_key) if local_key.exists() else None
    return decrypt_text(body, key_path=kp)


def _envsec_needs_update(sec_path: Path, env_text: str) -> bool:
    try:
        existing = _read_envsec_plaintext(sec_path)
    except Exception:
        return False
    return existing.rstrip("\n") != env_text.rstrip("\n")


def _maybe_offer_envsec_sync(*, context: str) -> bool:
    sec_path = Path.cwd() / ".env.sec"
    env_text = _build_uagent_env_text()
    if not env_text.strip():
        return False

    if sec_path.exists():
        if not _envsec_needs_update(sec_path, env_text):
            return False
        interactive = context == "cli" and bool(
            getattr(sys.stdin, "isatty", lambda: False)()
        )
        if interactive:
            prompt = (
                _(
                    "[INFO] .env.sec content does not match the current UAGENT_* environment variables. Update it? [y/N] "
                )
            )
            try:
                sys.__stdout__.write(prompt)
                sys.__stdout__.flush()
            except Exception:
                pass
            try:
                answer = input().strip().lower()
            except EOFError:
                answer = ""
            if answer not in ("y", "yes"):
                return False
        else:
            print(
                _(
                    "[INFO] .env.sec content does not match the current UAGENT_* environment variables. Use `uag_envsec` to update it."
                ),
                file=sys.__stderr__,
            )
            return False
    else:
        interactive = context == "cli" and bool(
            getattr(sys.stdin, "isatty", lambda: False)()
        )
        if interactive:
            prompt = (
                _(
                    "[INFO] .env.sec is missing. Create it from the current UAGENT_* environment variables? [y/N] "
                )
            )
            try:
                sys.__stdout__.write(prompt)
                sys.__stdout__.flush()
            except Exception:
                pass
            try:
                answer = input().strip().lower()
            except EOFError:
                answer = ""
            if answer not in ("y", "yes"):
                return False
        else:
            print(
                _(
                    "[INFO] .env.sec is missing. Use `uag_envsec` to create it from the current UAGENT_* environment variables."
                ),
                file=sys.__stderr__,
            )
            return False

    try:
        ensure_key_file()
        _write_text_atomic(sec_path, encrypt_text(env_text) + "\n")
        print("Created .env.sec: %(path)s" % {"path": sec_path}, file=sys.__stderr__)
        return True
    except Exception as e:
        print(
            "[WARN] Failed to create .env.sec: %(err)s" % {"err": e},
            file=sys.__stderr__,
        )
        return False


def validate_or_exit_startup_env(*, context: str) -> None:
    provider, missing, warnings = validate_startup_env()
    if missing:
        msg = format_missing_env_message(
            missing=missing, warnings=warnings, context=context
        )
        sys.__stderr__.write(msg)
        try:
            sys.__stderr__.flush()
        except Exception:
            pass
        sys.exit(2)
    if warnings:
        for w in warnings:
            print(
                _("[WARN] {message}", default="[WARN] {message}", message=w),
                file=sys.stderr,
            )

    _maybe_offer_envsec_sync(context=context)
