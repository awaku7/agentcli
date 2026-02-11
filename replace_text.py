#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple


DEFAULT_SKIP_DIRNAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
}


@dataclass
class FileResult:
    path: Path
    changed: bool
    replacements: int
    encoding_used: Optional[str]
    skipped_reason: Optional[str] = None


def is_probably_binary(path: Path, sniff_bytes: int = 8192) -> Tuple[bool, Optional[str]]:
    """
    バイナリっぽいかを簡易判定:
      - NUL(\x00) が含まれる -> ほぼバイナリ
      - 先頭sniff_bytes中の「非テキスト比率」が高い -> バイナリ扱い
    """
    try:
        data = path.read_bytes()[:sniff_bytes]
    except Exception as e:
        return True, f"read_error:{e}"

    if not data:
        return False, None  # 空ファイルはテキスト扱い

    if b"\x00" in data:
        return True, "contains_nul"

    # テキストに出やすい文字集合を広めに許容
    # (ASCII制御のうちタブ/改行/復帰は許可)
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
    nontext = data.translate(None, text_chars)
    ratio = len(nontext) / len(data)

    # 経験則: 30%超えはバイナリ寄りと判断
    return (ratio > 0.30), (f"nontext_ratio:{ratio:.2f}" if ratio > 0.30 else None)


def iter_files(root: Path, skip_dirnames: set[str], follow_symlinks: bool = False) -> Iterable[Path]:
    """
    root以下を再帰走査してファイルパスをyield
    """
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        dpath = Path(dirpath)

        # ディレクトリスキップ（in-placeで削ると walk が潜らなくなる）
        dirnames[:] = [d for d in dirnames if d not in skip_dirnames]

        for fn in filenames:
            yield dpath / fn


def read_text_with_fallback(
    path: Path,
    encoding: Optional[str],
    fallback_encodings: list[str],
) -> Tuple[str, str]:
    """
    encoding が指定されていればそれで読む。
    指定がなければ fallback_encodings を順に試す。
    成功した encoding を返す。
    """
    encodings_to_try = [encoding] if encoding else []
    encodings_to_try += [e for e in fallback_encodings if e != encoding]

    last_err: Optional[Exception] = None
    for enc in encodings_to_try:
        try:
            return path.read_text(encoding=enc), enc
        except Exception as e:
            last_err = e

    raise RuntimeError(f"failed to decode with encodings={encodings_to_try}: {last_err}")


def replace_in_file(
    path: Path,
    src: str,
    dst: str,
    dry_run: bool,
    encoding: Optional[str],
    fallback_encodings: list[str],
    newline: Optional[str],
) -> FileResult:
    is_bin, bin_reason = is_probably_binary(path)
    if is_bin:
        return FileResult(
            path=path,
            changed=False,
            replacements=0,
            encoding_used=None,
            skipped_reason=f"binary:{bin_reason}",
        )

    try:
        text, used_enc = read_text_with_fallback(path, encoding, fallback_encodings)
    except Exception as e:
        return FileResult(
            path=path,
            changed=False,
            replacements=0,
            encoding_used=None,
            skipped_reason=f"decode_error:{e}",
        )

    count = text.count(src)
    if count == 0:
        return FileResult(
            path=path,
            changed=False,
            replacements=0,
            encoding_used=used_enc,
            skipped_reason=None,
        )

    new_text = text.replace(src, dst)

    if not dry_run:
        # newline指定がある場合、改行コードを統一して書き戻す
        if newline is not None:
            new_text = new_text.replace("\r\n", "\n").replace("\r", "\n")
            new_text = new_text.replace("\n", newline)

        path.write_text(new_text, encoding=used_enc)

    return FileResult(
        path=path,
        changed=True,
        replacements=count,
        encoding_used=used_enc,
        skipped_reason=None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace text under a directory recursively (skips binary files). No backups are created."
    )
    parser.add_argument("root", help="Target root directory (recursive).")
    parser.add_argument("src", help="Source string to replace.")
    parser.add_argument("dst", help="Destination string.")
    parser.add_argument("--dry-run", action="store_true", help="Do not modify files; just report.")
    parser.add_argument(
        "--encoding",
        default=None,
        help="Force text encoding (e.g., utf-8). If omitted, fallback encodings are tried.",
    )
    parser.add_argument(
        "--fallback-encodings",
        default="utf-8,utf-8-sig,cp932,latin-1",
        help="Comma-separated fallback encodings when --encoding is not specified.",
    )
    parser.add_argument(
        "--skip-dirs",
        default=",".join(sorted(DEFAULT_SKIP_DIRNAMES)),
        help="Comma-separated directory names to skip (matched by directory name).",
    )
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follow symlinks in directory walk (default: False).",
    )
    parser.add_argument(
        "--newline",
        default=None,
        choices=[None, "lf", "crlf"],
        help="Normalize newlines when writing: lf or crlf. Default: keep as-is.",
    )

    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"root is not a directory: {root}")

    if args.src == "":
        raise SystemExit("src must not be empty (refuse to replace empty string).")

    skip_dirnames = set([d for d in args.skip_dirs.split(",") if d])
    fallback_encodings = [e.strip() for e in args.fallback_encodings.split(",") if e.strip()]

    newline_map = {"lf": "\n", "crlf": "\r\n", None: None}
    newline = newline_map[args.newline]

    results: list[FileResult] = []
    total_files = 0

    for fpath in iter_files(root, skip_dirnames=skip_dirnames, follow_symlinks=args.follow_symlinks):
        # symlinkファイルはスキップ（意図しない別場所を書き換えない）
        try:
            if fpath.is_symlink():
                results.append(
                    FileResult(
                        path=fpath,
                        changed=False,
                        replacements=0,
                        encoding_used=None,
                        skipped_reason="symlink",
                    )
                )
                continue
        except Exception as e:
            results.append(
                FileResult(
                    path=fpath,
                    changed=False,
                    replacements=0,
                    encoding_used=None,
                    skipped_reason=f"stat_error:{e}",
                )
            )
            continue

        if not fpath.is_file():
            continue

        total_files += 1
        r = replace_in_file(
            path=fpath,
            src=args.src,
            dst=args.dst,
            dry_run=args.dry_run,
            encoding=args.encoding,
            fallback_encodings=fallback_encodings,
            newline=newline,
        )
        results.append(r)

    changed = [r for r in results if r.changed]
    skipped = [r for r in results if (not r.changed and r.skipped_reason)]
    unchanged = [r for r in results if (not r.changed and not r.skipped_reason)]

    total_repl = sum(r.replacements for r in changed)

    print("==== Summary ====")
    print(f"Root              : {root}")
    print(f"Total files seen  : {total_files}")
    print(f"Changed files     : {len(changed)}")
    print(f"Total replacements: {total_repl}")
    print(f"Unchanged files   : {len(unchanged)}")
    print(f"Skipped files     : {len(skipped)}")
    print(f"Dry run           : {args.dry_run}")
    print(f"Src -> Dst        : {args.src!r} -> {args.dst!r}")
    print()

    if changed:
        print("==== Changed files ====")
        for r in changed:
            print(f"{r.path}  (repl={r.replacements}, enc={r.encoding_used})")
        print()

    if skipped:
        print("==== Skipped files ====")
        for r in skipped:
            print(f"{r.path}  ({r.skipped_reason})")
        print()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
