#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"scripts"/"tool_json_i18n_batch.py"
S=importlib.util.spec_from_file_location("tool_json_i18n_batch",P); assert S and S.loader
b=importlib.util.module_from_spec(S); sys.modules[S.name]=b; S.loader.exec_module(b)

def tok(v:Any)->str:
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))

files=[]
for d in b.DEFAULT_TOOL_DIRS: files += b._iter_tool_json_files(d,None)
files=sorted(set(files))
src={}; cat={}; mem=defaultdict(Counter); dec={}
for p in files:
    try: s=b._english_source(p); d=b._load_json_object(p)
    except Exception: continue
    src[p]=s; cat[p]=d
    for lang in b.SUPPORTED_TARGET_LOCALES:
        block=d.get(lang)
        if not isinstance(block,dict): continue
        for k,en in s.items():
            if k not in block: continue
            v=block[k]
            if b._is_missing_or_stale(en,v,key=str(k),force=False,skip_same_as_en=False): continue
            vt=tok(v); mem[(lang,tok(en))][vt]+=1; dec[vt]=v
filled=changed=0
for p in files:
    if p not in src: continue
    d=cat[p]; dirty=False
    for lang in b.SUPPORTED_TARGET_LOCALES:
        block=d.get(lang) if isinstance(d.get(lang),dict) else {}
        for k,en in src[p].items():
            cur=block.get(k)
            if not b._is_missing_or_stale(en,cur,key=str(k),force=False,skip_same_as_en=False): continue
            cand=mem.get((lang,tok(en)))
            if not cand: continue
            ranked=cand.most_common()
            if len(ranked)>1 and ranked[0][1]==ranked[1][1]: continue
            rep=dec[ranked[0][0]]
            if lang not in d or not isinstance(d.get(lang),dict): d[lang]={}; block=d[lang]
            block[k]=rep; filled+=1; dirty=True
    if dirty: b._dump_json(p,d); changed+=1
print(f"files_changed: {changed}")
print(f"units_backfilled: {filled}")
