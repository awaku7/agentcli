"""Compile gettext .po files to .mo.

Usage:
  python scripts/compile_locales.py

This script is intentionally small and dependency-free.

Notes:
- .po files in this repository are UTF-8.
- We implement only a tiny subset of msgfmt:
  - msgid/msgstr (no plural, no context)
  - multiline quoted strings supported
- We avoid using str.strip('"') for unquoting because it can drop quotes incorrectly.
  Instead we remove exactly one leading and one trailing double quote when present.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _compile_one(po_path: Path) -> None:
    import struct

    def unescape(s: str) -> str:
        """Unescape a .po quoted string content (without surrounding quotes).

        Supported escapes:
          \\"  -> "
          \\\\ -> \\ 
          \\n  -> newline
          \\t  -> tab
          \\r  -> carriage return

        Unknown escapes are preserved as-is (best-effort).
        """

        out: list[str] = []
        i = 0
        while i < len(s):
            ch = s[i]
            if ch != "\\":
                out.append(ch)
                i += 1
                continue

            i += 1
            if i >= len(s):
                out.append("\\")
                break

            esc = s[i]
            i += 1

            if esc == "n":
                out.append("\n")
            elif esc == "t":
                out.append("\t")
            elif esc == "r":
                out.append("\r")
            elif esc == "\\":
                out.append("\\")
            elif esc == '"':
                out.append('"')
            else:
                out.append("\\" + esc)

        return "".join(out)

    def unquote_po(token: str) -> str:
        """Remove exactly one pair of surrounding double quotes if present."""
        t = (token or "").strip()
        if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
            return t[1:-1]
        return t

    messages: dict[str, str] = {}

    msgid: list[str] = []
    msgstr: list[str] = []
    in_msgid = False
    in_msgstr = False

    def commit() -> None:
        nonlocal msgid, msgstr, in_msgid, in_msgstr
        if msgid:
            k = "".join(msgid)
            v = "".join(msgstr)
            messages[k] = v
        msgid = []
        msgstr = []
        in_msgid = False
        in_msgstr = False

    for raw in po_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("msgid "):
            commit()
            in_msgid = True
            in_msgstr = False
            token = line[6:].strip()
            msgid.append(unescape(unquote_po(token)))
            continue

        if line.startswith("msgstr "):
            in_msgid = False
            in_msgstr = True
            token = line[7:].strip()
            msgstr.append(unescape(unquote_po(token)))
            continue

        # continuation line: "..."
        if line.startswith('"') and line.endswith('"'):
            token = unquote_po(line)
            part = unescape(token)
            if in_msgid:
                msgid.append(part)
            elif in_msgstr:
                msgstr.append(part)
            continue

    commit()

    # Build .mo (GNU gettext) binary
    items = sorted(messages.items(), key=lambda kv: kv[0])
    ids = [k.encode("utf-8") for k, _v in items]
    strs = [v.encode("utf-8") for _k, v in items]

    magic = 0x950412DE
    version = 0
    n = len(items)
    o_msgid = 7 * 4
    o_msgstr = o_msgid + n * 8

    ids_pool_offset = o_msgstr + n * 8
    ids_offsets: list[tuple[int, int]] = []
    offset = ids_pool_offset
    for b in ids:
        ids_offsets.append((len(b), offset))
        offset += len(b) + 1

    strs_pool_offset = offset
    strs_offsets: list[tuple[int, int]] = []
    offset = strs_pool_offset
    for b in strs:
        strs_offsets.append((len(b), offset))
        offset += len(b) + 1

    out = bytearray()
    out += struct.pack("Iiiiiii", magic, version, n, o_msgid, o_msgstr, 0, 0)

    for ln, off in ids_offsets:
        out += struct.pack("ii", ln, off)
    for ln, off in strs_offsets:
        out += struct.pack("ii", ln, off)

    for b in ids:
        out += b + b"\x00"
    for b in strs:
        out += b + b"\x00"

    mo_path = po_path.with_suffix(".mo")
    mo_path.write_bytes(bytes(out))
    print(f"compiled: {po_path} -> {mo_path}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    locales_dir = repo_root / "src" / "uagent" / "locales"

    if not locales_dir.exists():
        print(f"locales dir not found: {locales_dir}", file=sys.stderr)
        return 1

    po_files = list(locales_dir.rglob("*.po"))
    if not po_files:
        print("no .po files found", file=sys.stderr)
        return 1

    for po in po_files:
        _compile_one(po)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
