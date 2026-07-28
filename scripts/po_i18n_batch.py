#!/usr/bin/env python
"""po_i18n_batch.py

Efficient batch i18n for host-side gettext .po files
(`src/uagent/locales/*/LC_MESSAGES/uag.po`).

Mirrors scripts/tool_json_i18n_batch.py:

  1) extract   - pull untranslated English msgid values into tmp/
  2) translate - call translate_text on value lists (placeholders protected)
  3) merge     - write translations back into msgstr only

Never send whole .po files to the translator. Only bare English strings.

Examples:
  python scripts/po_i18n_batch.py status --langs ja
  python scripts/po_i18n_batch.py extract --langs ja
  python scripts/po_i18n_batch.py translate --langs ja
  python scripts/po_i18n_batch.py merge --langs ja --apply
  python scripts/po_i18n_batch.py run --langs ja --apply

  # Force retranslate same-as-en / empty
  python scripts/po_i18n_batch.py run --langs ja,es --force --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCALES_DIR = ROOT / "src" / "uagent" / "locales"
DEFAULT_TMP_DIR = ROOT / "tmp" / "po_i18n"
PO_NAME = "uag.po"

PLACEHOLDER_RE = re.compile(
    r"%(?:\([^)]+\))?[#0\- +]?\d*(?:\.\d+)?[hlL]?[dsfr]|\{[A-Za-z_][A-Za-z0-9_]*\}"
)

MAX_TEXT_LEN = 10000
DEFAULT_BATCH_CHARS = 8000
DEFAULT_BATCH_ITEMS = 40


def _reconfigure_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass


def _norm_lang(code: str) -> str:
    c = (code or "").strip().replace("-", "_")
    if not c:
        return c
    parts = c.split("_", 1)
    if len(parts) == 1:
        return parts[0].lower()
    return f"{parts[0].lower()}_{parts[1].upper()}"


def _dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_json_object(path: Path) -> dict[str, Any]:
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"root is not object: {path}")
    return data


def _placeholders(s: str) -> set[str]:
    return set(PLACEHOLDER_RE.findall(s or ""))


def _import_polib():
    try:
        import polib  # type: ignore
    except ImportError as e:
        raise SystemExit("polib is required. Install with: pip install polib") from e
    return polib


def _po_path(locales_dir: Path, lang: str) -> Path:
    return locales_dir / lang / "LC_MESSAGES" / PO_NAME


def _discover_langs(locales_dir: Path) -> list[str]:
    out: list[str] = []
    if not locales_dir.is_dir():
        return out
    for p in sorted(locales_dir.iterdir()):
        if not p.is_dir():
            continue
        if p.name in ("en",):
            continue
        if _po_path(locales_dir, p.name).is_file():
            out.append(p.name)
    return out


def _parse_langs_arg(raw: str | None, locales_dir: Path) -> list[str]:
    if not raw or raw.strip() in ("*", "all"):
        return _discover_langs(locales_dir)
    langs = []
    for part in raw.split(","):
        lang = _norm_lang(part)
        if not lang or lang == "en":
            continue
        langs.append(lang)
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for lang in langs:
        if lang not in seen:
            seen.add(lang)
            out.append(lang)
    return out


def _entry_key(entry: Any) -> str:
    """Stable identity for a PO entry (msgctxt + msgid [+ plural])."""
    ctx = getattr(entry, "msgctxt", None) or ""
    mid = entry.msgid or ""
    plural = getattr(entry, "msgid_plural", None) or ""
    if plural:
        return f"{ctx}\x00{mid}\x00{plural}"
    return f"{ctx}\x00{mid}"


def _is_header(entry: Any) -> bool:
    return not (entry.msgid or "").strip() and not getattr(entry, "msgctxt", None)


def _is_candidate(
    entry: Any,
    *,
    force: bool,
    include_fuzzy: bool,
    skip_same_as_en: bool,
) -> bool:
    if entry.obsolete:
        return False
    if _is_header(entry):
        return False
    msgid = entry.msgid or ""
    if not msgid.strip():
        return False
    if len(msgid) > MAX_TEXT_LEN:
        return False

    flags = list(getattr(entry, "flags", []) or [])
    is_fuzzy = "fuzzy" in flags
    if is_fuzzy and not include_fuzzy and not force:
        # Still treat empty fuzzy as candidate when msgstr empty.
        if (entry.msgstr or "").strip():
            return False

    msgstr = entry.msgstr or ""
    if force:
        return True
    if not msgstr.strip():
        return True
    if skip_same_as_en and msgstr.strip() == msgid.strip():
        return True
    return False


@dataclass
class Unit:
    lang: str
    po_path: str
    entry_key: str
    msgid: str
    msgctxt: str
    occurrences: list[str]
    reason: str


def collect_units(
    locales_dir: Path,
    langs: list[str],
    *,
    force: bool,
    include_fuzzy: bool,
    skip_same_as_en: bool,
) -> list[Unit]:
    polib = _import_polib()
    units: list[Unit] = []
    for lang in langs:
        path = _po_path(locales_dir, lang)
        if not path.is_file():
            print(f"[skip] missing po: {path}", file=sys.stderr)
            continue
        po = polib.pofile(str(path))
        try:
            rel = path.resolve().relative_to(ROOT.resolve()).as_posix()
        except Exception:
            rel = path.as_posix()
        for entry in po:
            if not _is_candidate(
                entry,
                force=force,
                include_fuzzy=include_fuzzy,
                skip_same_as_en=skip_same_as_en,
            ):
                continue
            msgid = entry.msgid or ""
            msgstr = entry.msgstr or ""
            reason = "empty"
            if msgstr.strip() and msgstr.strip() == msgid.strip():
                reason = "same_as_en"
            elif "fuzzy" in (getattr(entry, "flags", []) or []):
                reason = "fuzzy"
            elif force:
                reason = "force"
            occ = []
            for oc in getattr(entry, "occurrences", []) or []:
                if isinstance(oc, (list, tuple)) and oc:
                    occ.append(f"{oc[0]}:{oc[1]}" if len(oc) > 1 else str(oc[0]))
                else:
                    occ.append(str(oc))
            units.append(
                Unit(
                    lang=lang,
                    po_path=rel,
                    entry_key=_entry_key(entry),
                    msgid=msgid,
                    msgctxt=str(getattr(entry, "msgctxt", None) or ""),
                    occurrences=occ[:8],
                    reason=reason,
                )
            )
    return units


def _job_dir(tmp_dir: Path, lang: str) -> Path:
    return tmp_dir / _norm_lang(lang)


def cmd_status(
    locales_dir: Path,
    langs: list[str],
    *,
    force: bool,
    include_fuzzy: bool,
    skip_same_as_en: bool,
) -> int:
    polib = _import_polib()
    print("lang\tentries\tempty\tsame_as_en\tfuzzy\tcandidates\tpo")
    total_cand = 0
    for lang in langs:
        path = _po_path(locales_dir, lang)
        if not path.is_file():
            print(f"{lang}\t-\t-\t-\t-\t-\tMISSING")
            continue
        po = polib.pofile(str(path))
        empty = same = fuzzy = cand = entries = 0
        for entry in po:
            if entry.obsolete or _is_header(entry):
                continue
            if not (entry.msgid or "").strip():
                continue
            entries += 1
            flags = list(getattr(entry, "flags", []) or [])
            if "fuzzy" in flags:
                fuzzy += 1
            ms = (entry.msgstr or "").strip()
            mid = (entry.msgid or "").strip()
            if not ms:
                empty += 1
            elif ms == mid:
                same += 1
            if _is_candidate(
                entry,
                force=force,
                include_fuzzy=include_fuzzy,
                skip_same_as_en=skip_same_as_en,
            ):
                cand += 1
        total_cand += cand
        print(f"{lang}\t{entries}\t{empty}\t{same}\t{fuzzy}\t{cand}\t{path.as_posix()}")
    print(f"TOTAL_CANDIDATES\t{total_cand}")
    return 0


def write_extract(units: list[Unit], tmp_dir: Path) -> dict[str, Path]:
    by_lang: dict[str, list[Unit]] = {}
    for u in units:
        by_lang.setdefault(u.lang, []).append(u)

    manifests: dict[str, Path] = {}
    for lang, items in sorted(by_lang.items()):
        d = _job_dir(tmp_dir, lang)
        d.mkdir(parents=True, exist_ok=True)
        # de-dupe identical msgid within a language (share one translation slot)
        # Keep first occurrence; map duplicates at merge via msgid text match too.
        unique_texts: list[str] = []
        text_index: dict[str, int] = {}
        manifest_items: list[dict[str, Any]] = []
        for u in items:
            if u.msgid not in text_index:
                text_index[u.msgid] = len(unique_texts)
                unique_texts.append(u.msgid)
            manifest_items.append(
                {
                    "id": text_index[u.msgid],
                    "entry_key": u.entry_key,
                    "po_path": u.po_path,
                    "msgctxt": u.msgctxt,
                    "msgid": u.msgid,
                    "occurrences": u.occurrences,
                    "reason": u.reason,
                }
            )
        man_path = d / "manifest.json"
        values_path = d / "values_en.json"
        _dump_json(
            man_path,
            {
                "lang": lang,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "entry_count": len(manifest_items),
                "unique_count": len(unique_texts),
                "items": manifest_items,
            },
        )
        _dump_json(values_path, unique_texts)
        preview_path = d / "preview.tsv"
        with preview_path.open("w", encoding="utf-8", newline="\n") as f:
            f.write("id\treason\tchars\tocc\tmsgid\n")
            # one row per unique text
            shown: set[int] = set()
            for item in manifest_items:
                i = int(item["id"])
                if i in shown:
                    continue
                shown.add(i)
                text = unique_texts[i]
                one = text.replace("\t", "\\t").replace("\n", "\\n")
                occ0 = ""
                if item.get("occurrences"):
                    occ0 = str(item["occurrences"][0])
                f.write(f"{i}\t{item.get('reason')}\t{len(text)}\t{occ0}\t{one}\n")
        manifests[lang] = man_path
        print(
            f"[extract] {lang}: {len(manifest_items)} entries / "
            f"{len(unique_texts)} unique -> {d}"
        )
    return manifests


def _chunk_indices(
    texts: list[str], *, max_chars: int, max_items: int
) -> list[list[int]]:
    batches: list[list[int]] = []
    cur: list[int] = []
    cur_chars = 0
    for i, t in enumerate(texts):
        add = len(t) + (1 if cur else 0)
        if cur and (len(cur) >= max_items or cur_chars + add > max_chars):
            batches.append(cur)
            cur = []
            cur_chars = 0
            add = len(t)
        cur.append(i)
        cur_chars += add
    if cur:
        batches.append(cur)
    return batches


def _import_translate_run_tool():
    sys.path.insert(0, str(ROOT / "src"))
    from uagent.tools.translate_text_tool import run_tool  # type: ignore

    return run_tool


def translate_lang(
    lang: str,
    tmp_dir: Path,
    *,
    source_lang: str,
    max_chars: int,
    max_items: int,
    sleep_s: float,
) -> Path:
    d = _job_dir(tmp_dir, lang)
    man_path = d / "manifest.json"
    values_path = d / "values_en.json"
    if not man_path.is_file() or not values_path.is_file():
        raise FileNotFoundError(f"missing extract for {lang}: run extract first ({d})")

    texts_raw = _load_json(values_path)
    if not isinstance(texts_raw, list):
        raise ValueError("values_en.json must be a list")
    texts = [str(x) for x in texts_raw]

    run_tool = _import_translate_run_tool()
    out: list[str | None] = [None] * len(texts)
    batches = _chunk_indices(texts, max_chars=max_chars, max_items=max_items)
    print(f"[translate] {lang}: {len(texts)} texts in {len(batches)} batch(es)")

    extra_terms = [
        "UAGENT_PROVIDER",
        "UAGENT_WORKDIR",
        "UAGENT_DEPNAME",
        "UAGENT_SHARED_MEMORY_FILE",
        "UAGENT_USE_TOOL",
        "UAGENT_LANG",
        "uag",
        "uagent",
        "translate_text",
        "tool_catalog",
        "tool_load",
        "finish_skill",
        "human_ask",
        "pwsh_exec",
        "bash_exec",
        "cmd_exec_json",
        "python_exec",
        ":model",
        ":help",
        ":tools",
        ":skills",
        ":plugin",
        ":auto",
        "Chat Completions",
        "Responses API",
        "OpenAI",
        "Azure",
        "Gemini",
        "Claude",
        "Grok",
        "Ollama",
        "DeepSeek",
    ]

    def _call_translate(batch_texts: list[str]) -> dict:
        payload = {
            "texts": batch_texts,
            "target_lang": lang,
            "source_lang": source_lang,
            "protect_placeholders": True,
            "protect_terms": True,
            "extra_protect_terms": extra_terms,
        }
        raw = run_tool(payload)
        try:
            res = json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"invalid JSON from translate_text: {e}: {raw[:300]}")
        if not res.get("ok", True) and res.get("error"):
            raise RuntimeError(f"translate error: {res.get('error')}")
        if res.get("error") and not res.get("translated"):
            raise RuntimeError(f"translate error: {res.get('error')}")
        return res

    def _translate_with_fallback(
        batch_texts: list[str], *, depth: int = 0
    ) -> list[str]:
        if not batch_texts:
            return []
        try:
            res = _call_translate(batch_texts)
            translated = res.get("translated")
            if isinstance(translated, list) and len(translated) == len(batch_texts):
                return [str(x) for x in translated]
            raise RuntimeError(
                "bad translated length (got "
                f"{0 if not isinstance(translated, list) else len(translated)}, "
                f"expected {len(batch_texts)})"
            )
        except Exception as e:
            msg = str(e)
            if len(batch_texts) == 1:
                print(f"    [warn] single-item failed, keeping EN: {msg[:160]}")
                return [batch_texts[0]]
            mid = max(1, len(batch_texts) // 2)
            if depth >= 8:
                out_parts: list[str] = []
                for one in batch_texts:
                    out_parts.extend(_translate_with_fallback([one], depth=depth + 1))
                    if sleep_s > 0:
                        time.sleep(min(sleep_s, 0.05))
                return out_parts
            print(
                f"    [fallback depth={depth}] {msg[:120]} -> split "
                f"{len(batch_texts)} into {mid}+{len(batch_texts) - mid}"
            )
            left = _translate_with_fallback(batch_texts[:mid], depth=depth + 1)
            if sleep_s > 0:
                time.sleep(sleep_s)
            right = _translate_with_fallback(batch_texts[mid:], depth=depth + 1)
            return left + right

    for bi, idxs in enumerate(batches, 1):
        batch_texts = [texts[i] for i in idxs]
        translated = _translate_with_fallback(batch_texts)
        if len(translated) != len(batch_texts):
            raise RuntimeError(
                f"batch {bi}: fallback produced {len(translated)} != {len(batch_texts)}"
            )
        for i, tr in zip(idxs, translated):
            out[i] = str(tr)
        print(f"  batch {bi}/{len(batches)}: {len(idxs)} items")
        if sleep_s > 0 and bi < len(batches):
            time.sleep(sleep_s)

    if any(x is None for x in out):
        missing = [i for i, x in enumerate(out) if x is None]
        raise RuntimeError(f"untranslated indices: {missing[:20]}")

    out_list = [x if x is not None else "" for x in out]
    out_path = d / "values_translated.json"
    _dump_json(out_path, out_list)

    man = _load_json_object(man_path)
    items = man.get("items") if isinstance(man, dict) else []
    qc = []
    if isinstance(items, list):
        # QC per unique id
        seen_ids: set[int] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            i = int(item.get("id", -1))
            if i < 0 or i in seen_ids or i >= len(out_list):
                continue
            seen_ids.add(i)
            en_text = texts[i]
            tr_text = out_list[i]
            en_ph = sorted(_placeholders(en_text))
            tr_ph = sorted(_placeholders(tr_text))
            qc.append(
                {
                    "id": i,
                    "placeholder_ok": en_ph == tr_ph,
                    "en_placeholders": en_ph,
                    "tr_placeholders": tr_ph,
                    "same_as_en": en_text.strip() == tr_text.strip(),
                    "chars_en": len(en_text),
                    "chars_tr": len(tr_text),
                    "sample_occ": (item.get("occurrences") or [None])[0],
                }
            )
    qc_path = d / "qc.json"
    _dump_json(
        qc_path,
        {
            "lang": lang,
            "count": len(out_list),
            "placeholder_mismatches": sum(1 for x in qc if not x["placeholder_ok"]),
            "same_as_en": sum(1 for x in qc if x["same_as_en"]),
            "items": qc,
        },
    )
    print(f"[translate] wrote {out_path} and {qc_path}")
    return out_path


def merge_lang(
    lang: str,
    tmp_dir: Path,
    locales_dir: Path,
    *,
    apply: bool,
    clear_fuzzy: bool,
) -> Path | None:
    polib = _import_polib()
    d = _job_dir(tmp_dir, lang)
    man = _load_json_object(d / "manifest.json")
    translated = _load_json(d / "values_translated.json")
    if not isinstance(translated, list):
        raise ValueError("values_translated.json must be a list")
    items = man.get("items")
    if not isinstance(items, list):
        raise ValueError("manifest.items missing")

    # id -> translated text
    # Also build entry_key -> text via items
    by_key: dict[str, str] = {}
    by_msgid: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        i = int(item.get("id", -1))
        if i < 0 or i >= len(translated):
            continue
        tr = str(translated[i])
        ek = str(item.get("entry_key") or "")
        mid = str(item.get("msgid") or "")
        if ek:
            by_key[ek] = tr
        if mid:
            by_msgid.setdefault(mid, tr)

    po_path = _po_path(locales_dir, lang)
    if not po_path.is_file():
        # fall back to path recorded in manifest
        for item in items:
            if isinstance(item, dict) and item.get("po_path"):
                cand = ROOT / str(item["po_path"])
                if cand.is_file():
                    po_path = cand
                    break
    if not po_path.is_file():
        raise FileNotFoundError(f"po not found for {lang}: {po_path}")

    po = polib.pofile(str(po_path))
    updated = 0
    skipped = 0
    for entry in po:
        if entry.obsolete or _is_header(entry):
            continue
        ek = _entry_key(entry)
        tr = by_key.get(ek)
        if tr is None:
            tr = by_msgid.get(entry.msgid or "")
        if tr is None:
            skipped += 1
            continue
        # placeholder safety: if broken, keep previous non-empty or msgid
        en_ph = _placeholders(entry.msgid or "")
        tr_ph = _placeholders(tr)
        if en_ph != tr_ph:
            print(
                f"[merge-warn] placeholder mismatch, keeping previous: "
                f"{(entry.msgid or '')[:60]!r}",
                file=sys.stderr,
            )
            skipped += 1
            continue
        if entry.msgstr == tr:
            continue
        entry.msgstr = tr
        if clear_fuzzy and "fuzzy" in (entry.flags or []):
            entry.flags = [f for f in entry.flags if f != "fuzzy"]
        updated += 1

    print(
        f"[merge] {lang}: updated={updated} unchanged_or_skipped~={skipped} "
        f"file={po_path}"
    )
    if apply:
        po.save(str(po_path))
        print(f"[merge] wrote {po_path}")
        return po_path
    print("[merge] dry-run (pass --apply to write)")
    return None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Batch-translate host gettext .po files via translate_text"
    )
    p.add_argument(
        "command",
        choices=["status", "extract", "translate", "merge", "run"],
        help="Pipeline step",
    )
    p.add_argument(
        "--langs",
        default="ja",
        help="Comma-separated langs, or 'all' (default: ja). 'en' is skipped.",
    )
    p.add_argument(
        "--locales-dir",
        type=Path,
        default=DEFAULT_LOCALES_DIR,
        help=f"Locales root (default: {DEFAULT_LOCALES_DIR})",
    )
    p.add_argument(
        "--tmp-dir",
        type=Path,
        default=DEFAULT_TMP_DIR,
        help=f"Temp dir (default: {DEFAULT_TMP_DIR})",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Include entries even if msgstr already differs / force retranslate",
    )
    p.add_argument(
        "--include-fuzzy",
        action="store_true",
        help="Include fuzzy entries with non-empty msgstr",
    )
    p.add_argument(
        "--keep-same-as-en",
        action="store_true",
        help="Do NOT treat same-as-en msgstr as candidate (default: treat as candidate)",
    )
    p.add_argument(
        "--source-lang",
        default="en",
        help="Source language for translate_text (default: en)",
    )
    p.add_argument(
        "--batch-chars",
        type=int,
        default=DEFAULT_BATCH_CHARS,
        help=f"Max chars per translate batch (default: {DEFAULT_BATCH_CHARS})",
    )
    p.add_argument(
        "--batch-items",
        type=int,
        default=DEFAULT_BATCH_ITEMS,
        help=f"Max items per translate batch (default: {DEFAULT_BATCH_ITEMS})",
    )
    p.add_argument(
        "--sleep",
        type=float,
        default=0.15,
        help="Sleep seconds between batches (default: 0.15)",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Actually write .po files on merge/run (default: dry-run for merge)",
    )
    p.add_argument(
        "--keep-fuzzy",
        action="store_true",
        help="Do not clear fuzzy flag on successful merge",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdout()
    args = build_parser().parse_args(argv)
    locales_dir: Path = args.locales_dir
    tmp_dir: Path = args.tmp_dir
    langs = _parse_langs_arg(args.langs, locales_dir)
    if not langs:
        print("No target languages resolved.", file=sys.stderr)
        return 2

    skip_same_as_en = not args.keep_same_as_en
    force = bool(args.force)
    include_fuzzy = bool(args.include_fuzzy)

    if args.command == "status":
        return cmd_status(
            locales_dir,
            langs,
            force=force,
            include_fuzzy=include_fuzzy,
            skip_same_as_en=skip_same_as_en,
        )

    if args.command in ("extract", "run"):
        units = collect_units(
            locales_dir,
            langs,
            force=force,
            include_fuzzy=include_fuzzy,
            skip_same_as_en=skip_same_as_en,
        )
        if not units:
            print("[extract] nothing to do")
            if args.command == "extract":
                return 0
        else:
            write_extract(units, tmp_dir)

    if args.command in ("translate", "run"):
        for lang in langs:
            d = _job_dir(tmp_dir, lang)
            if not (d / "values_en.json").is_file():
                print(f"[translate] skip {lang}: no extract", file=sys.stderr)
                continue
            values = _load_json(d / "values_en.json")
            if isinstance(values, list) and not values:
                print(f"[translate] skip {lang}: empty")
                _dump_json(d / "values_translated.json", [])
                continue
            translate_lang(
                lang,
                tmp_dir,
                source_lang=args.source_lang,
                max_chars=args.batch_chars,
                max_items=args.batch_items,
                sleep_s=args.sleep,
            )

    if args.command in ("merge", "run"):
        for lang in langs:
            d = _job_dir(tmp_dir, lang)
            if not (d / "values_translated.json").is_file():
                print(f"[merge] skip {lang}: no translated values", file=sys.stderr)
                continue
            merge_lang(
                lang,
                tmp_dir,
                locales_dir,
                apply=bool(args.apply),
                clear_fuzzy=not args.keep_fuzzy,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
