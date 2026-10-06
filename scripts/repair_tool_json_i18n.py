#!/usr/bin/env python
"""Repair empty or suspicious same-as-English values in tool JSON i18n files.

English source values are extracted from the matching Python source
(``_(key, default=...)``). Tool JSON contains non-English translations only.
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tool_json_i18n_batch import (  # noqa: E402
    SUPPORTED_TARGET_LOCALES,
    _english_source,
    _iter_tool_json_files,
)
from uagent.tools.translate_text_tool import run_tool  # noqa: E402

TOOLS_DIR = ROOT / "src" / "uagent" / "tools"
EXTRA_TERMS = [
    "protect_terms",
    "protect_placeholders",
    "extra_protect_terms",
    "target_lang",
    "source_lang",
    "output_path",
    "response_format",
    "x_search_terms",
    "translate_text",
    "audio_speech",
    "audio_transcribe",
    "alloy",
    "echo",
    "fable",
    "onyx",
    "nova",
    "shimmer",
    "ash",
    "ballad",
    "coral",
    "sage",
    "verse",
    "eve",
    "STDOUT",
    "STDERR",
    "returncode",
    "bash_exec",
    "pwsh_exec",
    "python_exec",
    "OpenAI",
    "Azure",
    "Grok",
    "xAI",
    "Google",
    "n8n",
    "uagent",
    "uag",
]


def _should_skip_same(text: str) -> bool:
    s = text.strip()
    if not s:
        return True
    if len(s) <= 3:
        return True
    if re.fullmatch(r"[A-Za-z0-9_\-+.]+", s) and len(s) <= 16:
        return True
    return False


def collect_jobs(files: list[Path]) -> list[tuple[str, str, str, int | None, str, str]]:
    jobs: list[tuple[str, str, str, int | None, str, str]] = []
    for fp in files:
        data = json.loads(fp.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        try:
            source = _english_source(fp)
        except ValueError:
            continue
        for lg, block in data.items():
            if lg not in SUPPORTED_TARGET_LOCALES or not isinstance(block, dict):
                continue
            for key, source_value in source.items():
                if key not in block:
                    continue
                localized = block[key]
                if isinstance(source_value, list) and isinstance(localized, list):
                    for index, english_text in enumerate(source_value):
                        if not isinstance(english_text, str) or not english_text.strip():
                            continue
                        if index >= len(localized):
                            # Search-term counts are locale-specific and may be shorter.
                            if key == "x_search_terms":
                                continue
                            localized_text = ""
                        else:
                            raw = localized[index]
                            localized_text = "" if raw is None else str(raw)
                        if not localized_text.strip():
                            jobs.append(
                                (str(fp), lg, key, index, english_text, "empty_list")
                            )
                        elif localized_text == english_text and not _should_skip_same(
                            english_text
                        ):
                            jobs.append(
                                (str(fp), lg, key, index, english_text, "same_list")
                            )
                    continue
                if isinstance(source_value, str) and isinstance(localized, str):
                    if not localized.strip() and source_value.strip():
                        jobs.append(
                            (str(fp), lg, key, None, source_value, "empty_str")
                        )
                    elif localized == source_value and not _should_skip_same(source_value):
                        jobs.append(
                            (str(fp), lg, key, None, source_value, "same_str")
                        )
    return jobs


def translate_batch(lang: str, texts: list[str]) -> list[str]:
    if not texts:
        return []
    raw = run_tool(
        {
            "texts": texts,
            "target_lang": lang,
            "source_lang": "en",
            "protect_placeholders": True,
            "protect_terms": True,
            "extra_protect_terms": EXTRA_TERMS,
        }
    )
    res = json.loads(raw)
    translated = res.get("translated")
    if (
        not res.get("error")
        and isinstance(translated, list)
        and len(translated) == len(texts)
        and all(str(item).strip() for item in translated)
    ):
        return [str(item) for item in translated]
    if len(texts) == 1:
        return texts[:]
    mid = max(1, len(texts) // 2)
    left = translate_batch(lang, texts[:mid])
    time.sleep(0.05)
    right = translate_batch(lang, texts[mid:])
    return left + right


def main() -> int:
    files = _iter_tool_json_files(TOOLS_DIR, None)
    jobs = collect_jobs(files)
    print(f"jobs={len(jobs)} files={len(files)}")
    print("by_kind", dict(Counter(job[5] for job in jobs)))
    print("by_lang", Counter(job[1] for job in jobs).most_common(8))

    by_lang: dict[str, list] = defaultdict(list)
    for job in jobs:
        by_lang[job[1]].append(job)

    file_data: dict[str, dict] = {
        str(fp): json.loads(fp.read_text(encoding="utf-8")) for fp in files
    }
    english_sources = {str(fp): _english_source(fp) for fp in files}

    cache: dict[tuple[str, str], str] = {}
    stats: Counter[str] = Counter()
    changed: set[str] = set()
    started = time.time()

    for lang in sorted(by_lang):
        lang_jobs = by_lang[lang]
        unique: list[str] = []
        seen: set[str] = set()
        for _fp, _lg, _key, _idx, english_text, _kind in lang_jobs:
            if english_text not in seen:
                seen.add(english_text)
                unique.append(english_text)
        print(f"[{lang}] jobs={len(lang_jobs)} unique={len(unique)}")

        index = 0
        batch_size = 6
        while index < len(unique):
            chunk = unique[index : index + batch_size]
            try:
                translations = translate_batch(lang, chunk)
            except Exception as exc:
                print(f"  batch fail {exc}; fallback singles")
                translations = []
                for one in chunk:
                    try:
                        translations.extend(translate_batch(lang, [one]))
                    except Exception:
                        translations.append(one)
                    time.sleep(0.05)
            for src, dst in zip(chunk, translations):
                cache[(lang, src)] = dst if str(dst).strip() else src
            index += len(chunk)
            if index % 30 == 0 or index >= len(unique):
                print(f"  unique {min(index, len(unique))}/{len(unique)}")
            time.sleep(0.1)

        for fp, lg, key, item_index, english_text, kind in lang_jobs:
            data = file_data[fp]
            block = data[lg]
            translated = cache.get((lg, english_text), english_text)
            if item_index is None:
                if block.get(key) != translated:
                    block[key] = translated
                    changed.add(fp)
                    stats[f"{kind}:applied"] += 1
                else:
                    stats[f"{kind}:same"] += 1
                continue

            values = block.get(key)
            if not isinstance(values, list):
                stats["bad_list"] += 1
                continue
            values = list(values)
            source_list = english_sources[fp].get(key)
            if not isinstance(source_list, list):
                stats["bad_source_list"] += 1
                continue
            if key == "x_search_terms" and item_index >= len(values):
                # Do not pad locale-specific search terms.
                continue
            while len(values) <= item_index:
                values.append("")
            if key != "x_search_terms" and len(values) < len(source_list):
                values.extend([""] * (len(source_list) - len(values)))
            if values[item_index] != translated:
                values[item_index] = translated
                block[key] = values
                changed.add(fp)
                stats[f"{kind}:applied"] += 1
            else:
                stats[f"{kind}:same"] += 1

    for fp in sorted(changed):
        path = Path(fp)
        backup = Path(str(path) + ".repair.bak")
        if not backup.exists():
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(
            json.dumps(file_data[fp], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"elapsed={time.time() - started:.1f}s changed_files={len(changed)}")
    print("stats", dict(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
