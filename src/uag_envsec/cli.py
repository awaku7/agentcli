from __future__ import annotations

"""CLI for encrypting and updating .env.sec files."""

import argparse
import getpass
import re
import sys
from pathlib import Path

from .secret_core import (
    DEFAULT_SEC_SUFFIX,
    decrypt_text,
    default_key_path,
    encrypt_text,
    ensure_key_file,
)

_ENV_KEY_RE = re.compile(
    r"^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=", re.MULTILINE
)


def _build_encrypt_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uag_envsec",
        description="Encrypt a .env file into .env.sec.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".env",
        help="Path to the input .env file (default: .env)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for the encrypted file (default: input path + .sec)",
    )
    parser.add_argument(
        "--key-file",
        default=None,
        help="Key file path (default: ~/.uag/uag_envsec_key)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists",
    )
    return parser


def _build_add_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uag_envsec add",
        description="Add or update a variable inside an encrypted .env.sec file.",
    )
    parser.add_argument(
        "--file",
        default=".env.sec",
        help="Path to the encrypted .env.sec file (default: .env.sec)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path (default: overwrite the input file)",
    )
    parser.add_argument(
        "--key-file",
        default=None,
        help="Key file path (default: ~/.uag/uag_envsec_key)",
    )
    parser.add_argument(
        "--key",
        default=None,
        help="Environment variable name",
    )
    parser.add_argument(
        "--value",
        default=None,
        help="Environment variable value",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists",
    )
    return parser


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


def _upsert_env_text(text: str, key: str, value: str) -> str:
    line = f"{key}={_format_env_value(value)}"
    lines = text.splitlines()
    for idx, current in enumerate(lines):
        match = _ENV_KEY_RE.match(current)
        if match and match.group("key") == key:
            lines[idx] = line
            break
    else:
        lines.append(line)

    updated = "\n".join(lines)
    if text.endswith(("\n", "\r")):
        return updated + "\n"
    return updated


def _read_key_value_from_args(args: argparse.Namespace) -> tuple[str, str]:
    if args.key is not None and args.value is not None:
        key = args.key.strip()
        value = args.value
        return key, value

    if args.key is not None and args.value is None:
        key = args.key.strip()
        value = getpass.getpass("Value: ")
        return key, value

    if args.key is None and args.value is not None:
        raise SystemExit("--value requires --key")

    key = input("Key: ").strip()
    if not key:
        raise SystemExit("Key is required")
    value = getpass.getpass("Value: ")
    return key, value


def _resolve_key_file(raw: str | None) -> Path:
    return Path(raw) if raw else default_key_path()


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _run_encrypt(args: argparse.Namespace) -> int:
    src_path = Path(args.path)
    if not src_path.exists():
        print(f"Input file not found: {src_path}", file=sys.stderr)
        return 1

    out_path = (
        Path(args.output) if args.output else Path(str(src_path) + DEFAULT_SEC_SUFFIX)
    )
    if out_path.exists() and not args.force:
        print(f"Output file already exists: {out_path} (use --force)", file=sys.stderr)
        return 1

    key_file = _resolve_key_file(args.key_file)
    ensure_key_file(key_file)
    encrypted = encrypt_text(src_path.read_text(encoding="utf-8"), key_path=key_file)
    _write_text_atomic(out_path, encrypted)
    print(str(out_path))
    return 0


def _run_add(args: argparse.Namespace) -> int:
    enc_path = Path(args.file)
    if not enc_path.exists():
        print(f"Encrypted file not found: {enc_path}", file=sys.stderr)
        return 1

    out_path = Path(args.output) if args.output else enc_path
    if (
        out_path.exists()
        and out_path.resolve() != enc_path.resolve()
        and not args.force
    ):
        print(f"Output file already exists: {out_path} (use --force)", file=sys.stderr)
        return 1

    key_file = _resolve_key_file(args.key_file)
    if not key_file.exists():
        print(f"Key file not found: {key_file}", file=sys.stderr)
        return 1

    key, value = _read_key_value_from_args(args)
    if not key:
        print("Key is required", file=sys.stderr)
        return 1
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        print(f"Invalid environment variable name: {key}", file=sys.stderr)
        return 1

    try:
        plaintext = decrypt_text(
            enc_path.read_text(encoding="utf-8").strip(), key_path=key_file
        )
    except Exception as exc:
        print(f"Failed to decrypt {enc_path}: {exc}", file=sys.stderr)
        return 1

    updated = _upsert_env_text(plaintext, key, value)
    _write_text_atomic(out_path, encrypt_text(updated, key_path=key_file))
    print(str(out_path))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "add":
        parsed = _build_add_parser().parse_args(args[1:])
        return _run_add(parsed)
    if args and args[0] == "encrypt":
        parsed = _build_encrypt_parser().parse_args(args[1:])
        return _run_encrypt(parsed)
    parsed = _build_encrypt_parser().parse_args(args)
    return _run_encrypt(parsed)


if __name__ == "__main__":
    raise SystemExit(main())
