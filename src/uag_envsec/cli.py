from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from .secret_core import DEFAULT_SEC_SUFFIX, encrypt_text, ensure_key_file


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uag_envsec",
        description="Encrypt a .env file into .env.sec",
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
        help="Key file path (default: current working directory key file)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    src_path = Path(args.path)
    if not src_path.exists():
        print(f"Input file not found: {src_path}", file=sys.stderr)
        return 1

    out_path = Path(args.output) if args.output else Path(str(src_path) + DEFAULT_SEC_SUFFIX)
    if out_path.exists() and not args.force:
        print(f"Output file already exists: {out_path} (use --force)", file=sys.stderr)
        return 1

    key_file = Path(args.key_file) if args.key_file else None
    if key_file is None:
        key_file = Path.cwd() / ".uagent.key"

    password = getpass.getpass("Password: ")
    ensure_key_file(key_file, password)
    encrypted = encrypt_text(src_path.read_text(encoding="utf-8"), password)
    out_path.write_text(encrypted, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
