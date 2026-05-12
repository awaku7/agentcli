from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping
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


def _unescape_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        inner = value[1:-1]
        out: list[str] = []
        i = 0
        while i < len(inner):
            ch = inner[i]
            if ch == "\\" and i + 1 < len(inner):
                nxt = inner[i + 1]
                if nxt == "n":
                    out.append("\n")
                elif nxt == "r":
                    out.append("\r")
                elif nxt == '"':
                    out.append('"')
                elif nxt == "\\":
                    out.append("\\")
                else:
                    out.append(nxt)
                i += 2
                continue
            out.append(ch)
            i += 1
        return "".join(out)
    return value


def _parse_uagent_env_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key.startswith("UAGENT_"):
            continue
        values[key] = _unescape_env_value(raw_value.strip())
    return values


def _build_uagent_env_text(
    env: Mapping[str, str] | None = None,
    prefix: str = "UAGENT_",
) -> str:
    source = os.environ if env is None else env
    keys = sorted(k for k in source if k.startswith(prefix))
    if not keys:
        return ""
    lines = [f"{key}={_format_env_value(source.get(key, ''))}" for key in keys]
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


def _snapshot_uagent_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = os.environ if env is None else env
    return {key: value for key, value in source.items() if key.startswith("UAGENT_")}


def _restore_uagent_env_snapshot(snapshot: Mapping[str, str] | None) -> None:
    if snapshot is None:
        return
    current_keys = [key for key in os.environ if key.startswith("UAGENT_")]
    for key in current_keys:
        if key in snapshot:
            os.environ[key] = snapshot[key]
        else:
            os.environ.pop(key, None)


def _maybe_offer_envsec_sync(
    *,
    context: str,
    env_snapshot: Mapping[str, str] | None = None,
) -> bool:
    sec_path = Path.cwd() / ".env.sec"
    snapshot = _snapshot_uagent_env(env_snapshot)

    if not snapshot and not sec_path.exists():
        return False

    sec_plain = ""
    if sec_path.exists():
        try:
            sec_plain = _read_envsec_plaintext(sec_path)
        except Exception as e:
            print(
                "[WARN] Failed to decrypt .env.sec: %(err)s" % {"err": e},
                file=sys.stderr,
            )
            return False

    sec_values = _parse_uagent_env_text(sec_plain) if sec_plain.strip() else {}

    if sec_path.exists():
        if not sec_values:
            return False

        diff_keys = [
            key
            for key, existing_value in sec_values.items()
            if key in snapshot and snapshot[key] != existing_value
        ]
        if not diff_keys:
            return False

        interactive = context == "cli" and bool(
            getattr(sys.stdin, "isatty", lambda: False)()
        )
        if interactive:
            prompt = _(
                "[INFO] .env.sec content does not match the current startup UAGENT_* environment variables. Update it? [y/N] "
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
                os.environ.update(sec_values)
                return False
        else:
            print(
                _(
                    "[INFO] .env.sec content does not match the current startup UAGENT_* environment variables. Use `uag_envsec` to update it."
                ),
                file=sys.__stderr__,
            )
            return False

        try:
            ensure_key_file()
            merged_values = dict(sec_values)
            merged_values.update(snapshot)
            plaintext = _build_uagent_env_text(merged_values)
            _write_text_atomic(sec_path, encrypt_text(plaintext) + "\n")
            os.environ.update(merged_values)
            print(_("Updated .env.sec: %(path)s", path=sec_path), file=sys.__stderr__)
            return True
        except Exception as e:
            print(
                _("[WARN] Failed to update .env.sec: %(err)s", err=e),
                file=sys.__stderr__,
            )
            return False

    interactive = context == "cli" and bool(
        getattr(sys.stdin, "isatty", lambda: False)()
    )
    if interactive:
        prompt = _(
            "[INFO] .env.sec is missing. Create it from the current startup UAGENT_* environment variables? [y/N] "
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
                "[INFO] .env.sec is missing. Use `uag_envsec` to create it from the current startup UAGENT_* environment variables."
            ),
            file=sys.__stderr__,
        )
        return False

    try:
        ensure_key_file()
        plaintext = _build_uagent_env_text(snapshot)
        _write_text_atomic(sec_path, encrypt_text(plaintext) + "\n")
        print(_("Created .env.sec: %(path)s", path=sec_path), file=sys.__stderr__)
        return True
    except Exception as e:
        print(
            _("[WARN] Failed to create .env.sec: %(err)s", err=e),
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

    try:
        from . import runtime_init as _runtime_init

        env_snapshot = _runtime_init.get_startup_uagent_env_snapshot()
    except Exception:
        env_snapshot = None

    _maybe_offer_envsec_sync(context=context, env_snapshot=env_snapshot)
