#!/usr/bin/env python
"""Repair empty / same-as-en values in tool JSON i18n files.

- Touches values only (keys/structure preserved)
- Uses translate_text with placeholder + term protection
- Caches by (lang, en_text)
- Backs up each changed file once as *.repair.bak
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

from uagent.tools.translate_text_tool import run_tool  # noqa: E402

TOOLS_DIR = ROOT / "src" / "uagent" / "tools"
LANG_RE = re.compile(r"^[a-z]{2}(?:_[A-Z]{2})?$")
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
    # pure technical token
    if re.fullmatch(r"[A-Za-z0-9_\-+.]+", s) and len(s) <= 16:
        return True
    return False


def collect_jobs(files: list[Path]) -> list[tuple[str, str, str, int | None, str, str]]:
    jobs: list[tuple[str, str, str, int | None, str, str]] = []
    for fp in files:
        data = json.loads(fp.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("en"), dict):
            continue
        en = data["en"]
        for lg, block in data.items():
            if lg == "en" or not isinstance(block, dict) or not LANG_RE.match(lg):
                continue
            for k, en_v in en.items():
                if k not in block:
                    continue
                lg_v = block[k]
                if isinstance(en_v, list) and isinstance(lg_v, list):
                    # normalize length in job application stage
                    for i, a in enumerate(en_v):
                        if not isinstance(a, str) or not a.strip():
                            continue
                        b = lg_v[i] if i < len(lg_v) else ""
                        b = "" if b is None else str(b)
                        if not b.strip():
                            jobs.append((str(fp), lg, k, i, a, "empty_list"))
                        elif b == a and not _should_skip_same(a):
                            jobs.append((str(fp), lg, k, i, a, "same_list"))
                    continue
                if isinstance(en_v, str) and isinstance(lg_v, str):
                    if not lg_v.strip() and en_v.strip():
                        jobs.append((str(fp), lg, k, None, en_v, "empty_str"))
                    elif lg_v == en_v and not _should_skip_same(en_v):
                        jobs.append((str(fp), lg, k, None, en_v, "same_str"))
    return jobs


def translate_batch(lang: str, texts: list[str]) -> list[str]:
    if not texts:
        return []
    if len(texts) == 1:
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
        if res.get("error") and not res.get("translated"):
            return texts[:]
        tr = res.get("translated") or texts
        out = str(tr[0]) if tr else texts[0]
        return [out if out.strip() else texts[0]]

    # try batch; on failure split
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
    tr = res.get("translated")
    if (
        not res.get("error")
        and isinstance(tr, list)
        and len(tr) == len(texts)
        and all(str(x).strip() for x in tr)
    ):
        return [str(x) for x in tr]

    mid = max(1, len(texts) // 2)
    left = translate_batch(lang, texts[:mid])
    time.sleep(0.05)
    right = translate_batch(lang, texts[mid:])
    return left + right


def main() -> int:
    files = sorted(TOOLS_DIR.glob("*_tool.json"))
    jobs = collect_jobs(files)
    print(f"jobs={len(jobs)} files={len(files)}")
    print("by_kind", dict(Counter(j[5] for j in jobs)))
    print("by_lang", Counter(j[1] for j in jobs).most_common(8))

    by_lang: dict[str, list] = defaultdict(list)
    for j in jobs:
        by_lang[j[1]].append(j)

    # load all json
    file_data: dict[str, dict] = {}
    for fp in files:
        file_data[str(fp)] = json.loads(fp.read_text(encoding="utf-8"))

    cache: dict[tuple[str, str], str] = {}
    stats: Counter[str] = Counter()
    changed: set[str] = set()
    t0 = time.time()

    for lang in sorted(by_lang):
        lang_jobs = by_lang[lang]
        uniq: list[str] = []
        seen: set[str] = set()
        for _fp, _lg, _k, _idx, en_text, _kind in lang_jobs:
            if en_text not in seen:
                seen.add(en_text)
                uniq.append(en_text)
        print(f"[{lang}] jobs={len(lang_jobs)} unique={len(uniq)}")

        # batch unique texts
        i = 0
        batch_n = 6
        while i < len(uniq):
            chunk = uniq[i : i + batch_n]
            try:
                trs = translate_batch(lang, chunk)
            except Exception as e:
                print(f"  batch fail {e}; fallback singles")
                trs = []
                for one in chunk:
                    try:
                        trs.extend(translate_batch(lang, [one]))
                    except Exception:
                        trs.append(one)
                    time.sleep(0.05)
            for src, dst in zip(chunk, trs):
                cache[(lang, src)] = dst if str(dst).strip() else src
            i += len(chunk)
            if i % 30 == 0 or i >= len(uniq):
                print(f"  unique {min(i,len(uniq))}/{len(uniq)}")
            time.sleep(0.1)

        # apply
        for fp, lg, k, idx, en_text, kind in lang_jobs:
            data = file_data[fp]
            block = data[lg]
            tr = cache.get((lg, en_text), en_text)
            if idx is None:
                if block.get(k) != tr:
                    block[k] = tr
                    changed.add(fp)
                    stats[f"{kind}:applied"] += 1
                else:
                    stats[f"{kind}:same"] += 1
            else:
                lst = block.get(k)
                if not isinstance(lst, list):
                    stats["bad_list"] += 1
                    continue
                lst = list(lst)
                while len(lst) <= idx:
                    lst.append("")
                # also pad to en length if needed
                en_list = data.get("en", {}).get(k)
                if isinstance(en_list, list) and len(lst) < len(en_list):
                    lst.extend([""] * (len(en_list) - len(lst)))
                if lst[idx] != tr:
                    lst[idx] = tr
                    block[k] = lst
                    changed.add(fp)
                    stats[f"{kind}:applied"] += 1
                else:
                    stats[f"{kind}:same"] += 1

    # write
    for fp in sorted(changed):
        p = Path(fp)
        bak = Path(str(p) + ".repair.bak")
        if not bak.exists():
            bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        p.write_text(
            json.dumps(file_data[fp], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"elapsed={time.time()-t0:.1f}s changed_files={len(changed)}")
    print("stats", dict(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
