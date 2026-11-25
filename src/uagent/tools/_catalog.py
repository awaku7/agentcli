"""Tool catalog search (``get_tool_catalog``) and CJK query tokenizers.

Split out of ``tools/__init__.py`` (speed-first plan, P0-3). The package's
``get_tool_catalog`` imports this module on the first catalog search, so
startup does not load it. Package-level names are read at call time.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import warnings
from typing import Any, Optional

from .._pip_auto import install_with_status as _auto_install
from ..env_utils import env_get
from .i18n_helper import get_locale

JanomeTokenizer = None
jieba = None
KiwiAnalyzer = None
_janome_initialized = False
_jieba_initialized = False
_kiwi_initialized = False


def _ensure_janome() -> bool:
    global JanomeTokenizer, _janome_initialized
    if _janome_initialized:
        return JanomeTokenizer is not None
    _janome_initialized = True
    if not _auto_install("janome", version_spec=">=0.5.0"):
        return False
    try:
        from janome.tokenizer import Tokenizer

        JanomeTokenizer = Tokenizer
    except Exception:
        JanomeTokenizer = None
    return JanomeTokenizer is not None


def _ensure_jieba() -> bool:
    global jieba, _jieba_initialized
    if _jieba_initialized:
        return jieba is not None
    _jieba_initialized = True
    if not _auto_install("jieba", version_spec=">=0.42.1"):
        return False
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"pkg_resources is deprecated as an API.*",
                category=UserWarning,
            )
            import jieba as jieba_module

        jieba = jieba_module
    except Exception:
        jieba = None
    return jieba is not None


def _ensure_kiwi() -> bool:
    global KiwiAnalyzer, _kiwi_initialized
    if _kiwi_initialized:
        return KiwiAnalyzer is not None
    _kiwi_initialized = True
    if not _auto_install("kiwipiepy", version_spec=">=0.10.0"):
        return False
    try:
        from kiwipiepy import Kiwi

        # Kiwi loads its model at construction time, so keep one
        # instance instead of rebuilding it for every catalog search.
        KiwiAnalyzer = Kiwi()
    except Exception:
        KiwiAnalyzer = None
    return KiwiAnalyzer is not None


# PyThaiNLP creates its data directory when its tokenizers/taggers are
# imported. Do not install/import it during every startup: Thai tokenization
# is only needed when a Thai query is actually searched. This avoids creating
# ``pythainlp-data`` in the user's current working directory on macOS and
# other platforms.
thai_word_tokenize = None
thai_pos_tag = None
_thai_nlp_initialized = False


def _ensure_thai_nlp() -> bool:
    global thai_word_tokenize, thai_pos_tag, _thai_nlp_initialized
    if _thai_nlp_initialized:
        return thai_word_tokenize is not None
    _thai_nlp_initialized = True
    if not os.environ.get("PYTHAINLP_DATA") and not os.environ.get(
        "PYTHAINLP_DATA_DIR"
    ):
        if sys.platform == "darwin":
            cache_root = os.path.expanduser("~/Library/Caches")
        elif os.name == "nt":
            cache_root = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.cache"))
        else:
            cache_root = os.environ.get(
                "XDG_CACHE_HOME", os.path.expanduser("~/.cache")
            )
        os.environ["PYTHAINLP_DATA"] = os.path.join(cache_root, "uag", "pythainlp-data")
    data_dir = os.path.abspath(
        os.path.expanduser(
            os.environ.get("PYTHAINLP_DATA") or os.environ.get("PYTHAINLP_DATA_DIR", "")
        )
    )
    legacy_dir = os.path.abspath(os.path.join(os.getcwd(), "pythainlp-data"))
    if os.path.isdir(legacy_dir) and legacy_dir != data_dir:
        try:
            os.makedirs(data_dir, exist_ok=True)
            shutil.copytree(legacy_dir, data_dir, dirs_exist_ok=True)
            shutil.rmtree(legacy_dir)
        except OSError:
            # A cache migration failure must not prevent normal startup.
            pass
    if not _auto_install("pythainlp", version_spec=">=5.3.4"):
        return False
    try:
        from pythainlp.tokenize import word_tokenize
        from pythainlp.tag import pos_tag

        thai_word_tokenize = word_tokenize
        thai_pos_tag = pos_tag
    except Exception:
        thai_word_tokenize = None
        thai_pos_tag = None
    return thai_word_tokenize is not None


def _expand_catalog_token(token: str) -> list[str]:
    t = (token or "").strip().lower()
    return [t] if t else []


def _collect_janome_query_terms(query: str) -> list[str]:
    q = (query or "").strip()
    if not q or not _ensure_janome():
        return []
    try:
        jt = JanomeTokenizer()
        out: list[str] = []
        for t in jt.tokenize(q):
            pos = str(getattr(t, "part_of_speech", "") or "").split(",", 1)[0]
            if pos not in {"名詞", "動詞", "Noun", "Verb"}:
                continue
            term = str(getattr(t, "base_form", "") or "").strip().lower()
            if not term or term == "*":
                term = str(getattr(t, "surface", "") or "").strip().lower()
            if term:
                out.append(term)
        return out
    except Exception:
        return []


def _collect_jieba_query_terms(query: str) -> list[str]:
    q = (query or "").strip()
    if not q or not _ensure_jieba():
        return []
    try:
        out: list[str] = []
        for tok in jieba.lcut(q):
            term = str(tok or "").strip().lower()
            if term and not term.isspace():
                out.append(term)
        return out
    except Exception:
        return []


def _collect_thai_query_terms(query: str) -> list[str]:
    q = (query or "").strip()
    if not q or not _ensure_thai_nlp():
        return []
    try:
        out: list[str] = []
        tokens = list(thai_word_tokenize(q, engine="newmm"))
        if thai_pos_tag is not None:
            try:
                tags = thai_pos_tag(tokens, engine="perceptron", corpus="orchid")
            except Exception:
                tags = [(tok, "") for tok in tokens]
        else:
            tags = [(tok, "") for tok in tokens]
        for tok, pos in tags:
            term = str(tok or "").strip().lower()
            if not term or term.isspace():
                continue
            if pos and not str(pos).startswith(("N", "V")):
                continue
            out.append(term)
        return out
    except Exception:
        return []


def _collect_kiwi_query_terms(query: str) -> list[str]:
    q = (query or "").strip()
    if not q or not _ensure_kiwi():
        return []
    try:
        out: list[str] = []
        for t in KiwiAnalyzer.tokenize(q):
            form = str(getattr(t, "form", "") or "").strip().lower()
            tag = str(getattr(t, "tag", "") or "")
            if not form:
                continue
            if tag.startswith("N"):
                out.append(form)
            elif tag.startswith(("VV", "VA")):
                base = str(getattr(t, "base_form", "") or "").strip().lower()
                out.append(base if base and base != form else form + "다")
        return out
    except Exception:
        return []


def _has_japanese_script(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff]", text))


def _has_korean_script(text: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7a3\u1100-\u11ff]", text))


def _has_thai_script(text: str) -> bool:
    return bool(re.search(r"[\u0e00-\u0e7f]", text))


def _has_cjk_script(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _tokenize_catalog_query(query: str) -> list[str]:
    q = (query or "").strip().lower()
    if not q:
        return []

    loc = get_locale()
    base_tokens = [tok for tok in re.split(r"\s+", q) if tok]
    tokens: list[str] = []

    if _has_thai_script(q):
        tokens.extend(_collect_thai_query_terms(q))
    elif _has_japanese_script(q):
        tokens.extend(_collect_janome_query_terms(q))
    elif _has_korean_script(q):
        tokens.extend(_collect_kiwi_query_terms(q))
    elif _has_cjk_script(q):
        if loc.startswith("zh"):
            tokens.extend(_collect_jieba_query_terms(q))
        elif loc.startswith("ja"):
            tokens.extend(_collect_janome_query_terms(q))
        else:
            tokens.extend(_collect_jieba_query_terms(q))
    else:
        tokens.extend(base_tokens)

    tokens.extend(base_tokens)
    tokens.append(q)

    expanded: list[str] = []
    seen = set()
    for tok in tokens:
        for e in _expand_catalog_token(tok):
            if e not in seen:
                seen.add(e)
                expanded.append(e)

    return expanded


def _collect_search_terms(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        term = value.strip()
        return [term] if term else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_collect_search_terms(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_collect_search_terms(item))
        return out
    term = str(value).strip()
    return [term] if term else []


def get_tool_catalog(
    *,
    query: str,
    max_results: int = 12,
    tool_specs: Optional[list[dict[str, Any]]] = None,
    all_items: bool = False,
) -> list[dict[str, Any]]:
    """Return a lightweight searchable catalog of tools.

    If all_items is True, return all loaded + unloaded tools without query filtering.
    """
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        get_tool_specs,
        is_computer_use_conflict,
        _is_embedded_mode,
        _load_lazy_tool_spec,
        _sub_agent_job_tools_visible,
        _EMBEDDED_EXCLUDED_TOOLS,
        _LAZY_TOOL_MODULES,
        _SUB_AGENT_JOB_TOOL_NAMES,
    )

    q = (query or "").strip().lower() if not all_items else ""
    try:
        limit = int(max_results)
    except Exception:
        limit = 12
    if limit <= 0:
        limit = 12
    if all_items:
        limit = None

    debug_tools = str(env_get("UAGENT_DEBUG_TOOLS", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    tokens = _tokenize_catalog_query(q) if q else []
    if debug_tools:
        try:
            print(
                f"[TOOLCAT] query={q!r} tokens={tokens!r} limit={limit} all_items={all_items}",
                flush=True,
            )
        except Exception:
            pass

    specs = get_tool_specs() if tool_specs is None else tool_specs
    from ._tool_load_util import is_tool_loadable

    # Build set of loaded tool names for dedup
    loaded_names: set[str] = set()
    for spec in specs or []:
        fn = spec.get("function") or {}
        if isinstance(fn, dict):
            n = str(fn.get("name") or "").strip()
            if n:
                loaded_names.add(n)

    rows: list[dict[str, Any]] = []

    def _score_spec(
        name: str,
        description: str,
        param_names: list[str],
        search_terms_en: list[str],
        search_terms: list[str],
    ) -> int:
        if not q:
            return 1
        s = 0
        st = search_terms_en + search_terms
        sh = " ".join([p for p in st if p]).lower()
        hp = [name, description] + param_names + st
        hs = " ".join([p for p in hp if p]).lower()
        search_hit = False
        for tok in tokens:
            if tok in sh:
                search_hit = True
                s += 200
            if tok == name.lower():
                s += 100
            elif tok in name.lower():
                s += 40
            if tok in description.lower():
                s += 15
            for pn in param_names:
                pnl = pn.lower()
                if tok == pnl:
                    s += 20
                elif tok in pnl:
                    s += 8
        if q in sh:
            search_hit = True
            s += 400
        if q in hs:
            s += 25
        if search_hit:
            s += 1000
        # ``file_grep`` is a low-level line/pattern searcher. Keep it below
        # filename-oriented tools for broad queries such as "search files";
        # promote it only when the request explicitly mentions grep, regex,
        # patterns, lines, or content matching.
        if name == "file_grep":
            grep_intent = {
                "grep",
                "regex",
                "regexp",
                "pattern",
                "patterns",
                "line",
                "lines",
                "content",
                "literal",
            }
            if any(token in grep_intent for token in tokens) or name.lower() in tokens:
                # Explicit grep/name intent must outrank generic replacement tools.
                s += 500
            else:
                s -= 2000
        return s

    # 1. Process loaded tools
    for spec in specs or []:
        if not isinstance(spec, dict):
            continue
        fn = spec.get("function") or {}
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        description = str(fn.get("description") or "").strip()
        parameters = fn.get("parameters") or {}
        properties = parameters.get("properties") or {}
        required = parameters.get("required") or []
        param_names = list(properties.keys()) if isinstance(properties, dict) else []
        st_en = _collect_search_terms(fn.get("x_search_terms_en"))
        st = _collect_search_terms(fn.get("x_search_terms"))
        score = _score_spec(name, description, param_names, st_en, st)
        if score <= 0 and q:
            continue
        rows.append(
            {
                "name": name,
                "description": description,
                "required": (
                    [str(x) for x in required] if isinstance(required, list) else []
                ),
                "parameters": param_names,
                "loaded": True,
                "score": score,
            }
        )

    # 2. Also search unloaded tool modules (for discovery)
    if q or all_items:
        try:
            from ._tool_load_util import _find_tool_modules

            for _mname, mod in _find_tool_modules(skip_lazy=True):
                spec = getattr(mod, "TOOL_SPEC", None)
                if not isinstance(spec, dict):
                    continue
                if is_computer_use_conflict(spec):
                    continue
                if not is_tool_loadable(spec, mod):
                    continue
                fn = spec.get("function") or {}
                if not isinstance(fn, dict):
                    continue
                name = str(fn.get("name") or "").strip()
                if not name or name in loaded_names:
                    continue
                if _is_embedded_mode() and name in _EMBEDDED_EXCLUDED_TOOLS:
                    continue
                description = str(fn.get("description") or "").strip()
                parameters = fn.get("parameters") or {}
                properties = parameters.get("properties") or {}
                param_names = (
                    list(properties.keys()) if isinstance(properties, dict) else []
                )
                st_en = _collect_search_terms(fn.get("x_search_terms_en"))
                st = _collect_search_terms(fn.get("x_search_terms"))
                score = _score_spec(name, description, param_names, st_en, st)
                if score <= 0 and q:
                    continue
                rows.append(
                    {
                        "name": name,
                        "description": description,
                        "required": [],
                        "parameters": param_names,
                        "loaded": False,
                        "score": score - 100 if q else 0,
                    }
                )
        except Exception:
            pass

    # 3. Also search lazy-loaded tool specs (fast: read .spec.json or use already-imported module)
    if q or all_items:
        # Collect names already added by sections 1/2 for dedup
        _cataloged_names = {r["name"] for r in rows if r.get("name")}
        _lazy_locale = get_locale()

        # Scan for lazy modules using fast file check (_is_lazy_module reads
        # only the first few lines; os.scandir is a single directory read).
        _lazy_mod_names: list[str] = []
        try:
            from ._tool_load_util import _is_lazy_module

            _pkg_dir = os.path.dirname(__file__)
            for _entry in os.scandir(_pkg_dir):
                if _entry.name.endswith("_tool.py") and not _entry.name.startswith("_"):
                    _mn = _entry.name[:-3]
                    if _is_lazy_module(_mn):
                        _lazy_mod_names.append(_mn)
        except Exception:
            _lazy_mod_names = list(_LAZY_TOOL_MODULES)  # fallback

        for mod_name in _lazy_mod_names:
            # Try .spec.json first (fast, no import)
            spec = _load_lazy_tool_spec(mod_name)
            if not spec:
                # No .spec.json; try already-imported module (lazy tools are
                # still imported during _load_plugins() even if disabled).
                _full = f"uagent.tools.{mod_name}"
                _mod = sys.modules.get(_full)
                if _mod is not None:
                    spec = getattr(_mod, "TOOL_SPEC", None)
                if not isinstance(spec, dict):
                    continue
            if not is_tool_loadable(spec, _mod if "_mod" in locals() else None):
                continue
            fn = spec.get("function", {})
            if not isinstance(fn, dict):
                continue
            name = str(fn.get("name") or "").strip()
            if not name or name in loaded_names or name in _cataloged_names:
                continue
            if _is_embedded_mode() and name in _EMBEDDED_EXCLUDED_TOOLS:
                continue
            # Use locale-aware description if available
            _i18n = spec.get("i18n", {}) if isinstance(spec, dict) else {}
            _td_key = "tool.description"
            _td = _i18n.get(_td_key, {}) if isinstance(_i18n, dict) else {}
            if isinstance(_td, dict) and _lazy_locale in _td:
                description = str(_td[_lazy_locale])
            else:
                description = str(fn.get("description") or "").strip()
            parameters = fn.get("parameters", {})
            properties = parameters.get("properties", {})
            param_names = (
                list(properties.keys()) if isinstance(properties, dict) else []
            )
            st_en = _collect_search_terms(fn.get("x_search_terms_en"))
            st = _collect_search_terms(fn.get("x_search_terms"))
            score = _score_spec(name, description, param_names, st_en, st)
            if score <= 0 and q:
                continue
            rows.append(
                {
                    "name": name,
                    "description": description,
                    "required": [],
                    "parameters": param_names,
                    "loaded": False,
                    "score": score - 100 if q else 0,
                }
            )

    if not _sub_agent_job_tools_visible():
        rows = [row for row in rows if row.get("name") not in _SUB_AGENT_JOB_TOOL_NAMES]
    rows.sort(key=lambda x: (-int(x.get("score", 0)), str(x.get("name", ""))))

    out: list[dict[str, Any]] = []
    for row in rows[:limit]:
        out.append(
            {
                "name": row["name"],
                "description": row["description"],
                "required": row["required"],
                "parameters": row["parameters"],
                "loaded": row["loaded"],
            }
        )

    # Ensure web_search and fetch_url are always included in catalog results
    if not any(r["name"] == "search_web" for r in out):
        try:
            from ._tool_load_util import _find_tool_modules

            for _mname, mod in _find_tool_modules(skip_lazy=True):
                spec = getattr(mod, "TOOL_SPEC", None)
                if not isinstance(spec, dict):
                    continue
                fn = spec.get("function") or {}
                if not isinstance(fn, dict):
                    continue
                if fn.get("name") != "search_web":
                    continue
                description = str(fn.get("description") or "").strip()
                parameters = fn.get("parameters") or {}
                properties = parameters.get("properties") or {}
                required = parameters.get("required") or []
                param_names = (
                    list(properties.keys()) if isinstance(properties, dict) else []
                )
                out.append(
                    {
                        "name": "search_web",
                        "description": description,
                        "required": (
                            [str(x) for x in required]
                            if isinstance(required, list)
                            else []
                        ),
                        "parameters": param_names,
                        "loaded": False,
                    }
                )
                break
        except Exception:
            pass

    # Ensure fetch_url is always included in catalog results
    if not any(r["name"] == "fetch_url" for r in out):
        try:
            from ._tool_load_util import _find_tool_modules

            for _mname, mod in _find_tool_modules(skip_lazy=True):
                spec = getattr(mod, "TOOL_SPEC", None)
                if not isinstance(spec, dict):
                    continue
                fn = spec.get("function") or {}
                if not isinstance(fn, dict):
                    continue
                if fn.get("name") != "fetch_url":
                    continue
                description = str(fn.get("description") or "").strip()
                parameters = fn.get("parameters") or {}
                properties = parameters.get("properties") or {}
                required = parameters.get("required") or []
                param_names = (
                    list(properties.keys()) if isinstance(properties, dict) else []
                )
                out.append(
                    {
                        "name": "fetch_url",
                        "description": description,
                        "required": (
                            [str(x) for x in required]
                            if isinstance(required, list)
                            else []
                        ),
                        "parameters": param_names,
                        "loaded": False,
                    }
                )
                break
        except Exception:
            pass

    if debug_tools:
        try:
            print(
                f"[TOOLCAT] matched={[(r['name'], r['score'], r['loaded']) for r in rows[:limit]]}",
                flush=True,
            )
        except Exception:
            pass
    return out
