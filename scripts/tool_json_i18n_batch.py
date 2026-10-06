#!/usr/bin/env python
"""tool_json_i18n_batch.py

Efficient batch i18n for tool-side JSON files (`src/uagent/tools/*_tool.json`).

Workflow (tmp-based, structure-safe):
  1) extract  - pull missing English values into tmp/ (keys + values only)
  2) translate - call translate_text on value lists (placeholders protected)
  3) merge    - write translations back into *_tool.json language blocks

Why tmp?
  - Never feed whole JSON objects to the translator (keys/structure stay intact)
  - Resume-friendly: extract once, translate in chunks, merge when ready
  - Easy QC of intermediate files before touching source JSON

Examples:
  # Dry-run: show missing keys for ja/es
  python scripts/tool_json_i18n_batch.py status --langs ja,es

  # Full pipeline for one tool + one language
  python scripts/tool_json_i18n_batch.py run \\
      --tools translate_text --langs ja --apply

  # Extract only (inspect tmp first)
  python scripts/tool_json_i18n_batch.py extract --langs de,fr

  # Translate already-extracted payloads
  python scripts/tool_json_i18n_batch.py translate --langs de

  # Merge translated payloads into tool JSON (writes source files)
  python scripts/tool_json_i18n_batch.py merge --langs de --apply

  # Force retranslate even if target key exists
  python scripts/tool_json_i18n_batch.py run --langs ja --force --apply
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOOLS_DIR = ROOT / "src" / "uagent" / "tools"
DEFAULT_TOOL_DIRS = (DEFAULT_TOOLS_DIR, ROOT / "src" / "uagent" / "tools_rust")
DEFAULT_TMP_DIR = ROOT / "tmp" / "tool_json_i18n"

SUPPORTED_TOOL_LOCALES = (
    "ar",
    "bn",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "es",
    "fa",
    "fi",
    "fil",
    "fr",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "mn",
    "mr",
    "ms",
    "nb",
    "nl",
    "nn",
    "pl",
    "pt",
    "pt_BR",
    "ro",
    "ru",
    "sv",
    "sw",
    "th",
    "tr",
    "uk",
    "vi",
    "zh_CN",
    "zh_TW",
)
SUPPORTED_TARGET_LOCALES = tuple(
    lang for lang in SUPPORTED_TOOL_LOCALES if lang != "en"
)

LANG_KEY_RE = re.compile(r"^[a-z]{2,3}(?:_[A-Za-z]{2})?$")
PRINTF_PLACEHOLDER_RE = re.compile(
    r"%\((?P<name>[A-Za-z0-9_]+)\)[#0 +\-]?[0-9]*(?:\.[0-9]+)?[diouxXeEfFgGcrs]"
)
FORMATTER = Formatter()
BRACE_FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PIP_INSTALL_PREFIX_RE = re.compile(r"\bpip\s+install\b")
PIP_REQUIREMENT_NAME_RE = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)")
PIP_COMMAND_TRAILING_PUNCTUATION = ".,;:!?。；：！？"

# translate_text hard limit per element
MAX_TEXT_LEN = 10000
# Keep batches comfortably under API/join limits
DEFAULT_BATCH_CHARS = 8000
DEFAULT_BATCH_ITEMS = 40

# Search terms are locale-specific keyword sets. They may intentionally contain
# a different number of entries from English; x_search_terms_en is the runtime
# English fallback.
VARIABLE_LENGTH_LIST_KEYS = frozenset({"x_search_terms"})
INTENTIONAL_ENGLISH_TOOL_KEYS = frozenset(
    {
        # Protocol/debug/output templates whose English spelling is part of the
        # stable wire/log representation rather than user-facing prose.
        ("pybitchat_shared", "bitchat.debug_noise_hs"),
        ("pybitchat_shared", "bitchat.debug_noise_enc"),
        ("pybitchat_shared", "bitchat.debug_hs_start"),
        ("pybitchat_shared", "bitchat.debug_hs_msg1_sent"),
        ("pybitchat_shared", "bitchat.debug_hs_skip"),
        ("pybitchat_shared", "bitchat.nostr_msg"),
        ("pybitchat_shared", "bitchat.noise_dm_msg"),
        ("pybitchat_shared", "bitchat.mesh_msg"),
        ("pybitchat_shared", "bitchat.dm_msg"),
        ("vision_openai", "vision.error_prefix"),
        ("skill_history", "skill.ok"),
        ("create_tool", "cmd.help"),
        ("human_ask", "ui.footer"),
        ("safe_exec_ops", "ui.fallback_prompt"),
        ("safe_exec_ops", "ui.confirm.footer"),
        ("safe_file_ops", "ui.confirm.footer"),
        ("pybitchat_subscribe", "peers.list_entry"),
        ("pybitchat_subscribe", "geo.list_geohash"),
        ("pybitchat_subscribe", "geo.list_peer_id"),
        ("pybitchat_subscribe", "geo.joined_peer_id"),
        ("pybitchat_subscribe", "geo.joined_coords"),
        ("pybitchat_subscribe", "cmd.status_peer"),
        ("pybitchat_subscribe", "cmd.node_started_nostr_failed"),
        ("pybitchat_subscribe", "cmd.status_nostr_stopped"),
        ("pybitchat_subscribe", "cmd.status_nostr_relay"),
        ("pybitchat_subscribe", "cmd.status_nostr_pubkey"),
        ("pybitchat_subscribe", "geo.channel_entry"),
        ("search_files", "match.line"),
        ("current_location", "src.nmea"),
        ("wttrin", "output.forecast_row"),
        ("graph_rag_search", "out.db"),
        ("set_timer", "out.list_os_item"),
        ("ucp_checkout", "param.mode.description"),
        ("diff_files", "label.text_input"),
    }
)


def _is_intentional_english_tool_key(tool: str, key: str) -> bool:
    return (tool, key) in INTENTIONAL_ENGLISH_TOOL_KEYS



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


def _is_lang_block(key: str, value: Any) -> bool:
    return bool(LANG_KEY_RE.match(key)) and isinstance(value, dict)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_json_object(path: Path) -> dict[str, Any]:
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"root is not object: {path}")
    return data


def _dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _is_tool_i18n_catalog(path: Path, data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if any(isinstance(data.get(lang), dict) for lang in SUPPORTED_TARGET_LOCALES):
        return True
    try:
        return bool(_english_source(path))
    except ValueError:
        return False


def _iter_tool_json_files(tools_dir: Path, tools_filter: set[str] | None) -> list[Path]:
    files = sorted(tools_dir.glob("*.json"))
    out: list[Path] = []
    for p in files:
        try:
            data = _load_json(p)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not _is_tool_i18n_catalog(p, data):
            continue
        name = p.name
        stem = name[: -len("_tool.json")] if name.endswith("_tool.json") else p.stem
        if (
            tools_filter
            and stem not in tools_filter
            and p.stem not in tools_filter
            and name not in tools_filter
        ):
            continue
        out.append(p)
    return out


def _static_eval(node: ast.AST, constants: dict[str, Any]) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        pass
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_eval(node.left, constants)
        right = _static_eval(node.right, constants)
        try:
            return left + right
        except TypeError:
            return None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                parts.append(part.value)
                continue
            if not isinstance(part, ast.FormattedValue):
                return None
            value = _static_eval(part.value, constants)
            if not isinstance(value, (str, int, float, bool)):
                return None
            format_spec = ""
            if part.format_spec is not None:
                spec = _static_eval(part.format_spec, constants)
                if not isinstance(spec, str):
                    return None
                format_spec = spec
            try:
                parts.append(format(value, format_spec))
            except (TypeError, ValueError):
                return None
        return "".join(parts)
    return None


def _extract_english_source(py_path: Path) -> dict[str, Any]:
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError(f"cannot parse Python source {py_path}: {exc}") from exc

    constants: dict[str, Any] = {}
    for statement in tree.body:
        name: str | None = None
        value_node: ast.AST | None = None
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            name = statement.targets[0].id
            value_node = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            name = statement.target.id
            value_node = statement.value
        if name and value_node is not None:
            value = _static_eval(value_node, constants)
            if value is not None:
                constants[name] = value

    source: dict[str, Any] = {}
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    calls.sort(
        key=lambda node: (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))
    )
    for node in calls:
        if not isinstance(node.func, ast.Name) or node.func.id != "_" or not node.args:
            continue
        key_node = node.args[0]
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            continue
        default_node = next(
            (kw.value for kw in node.keywords if kw.arg == "default"),
            None,
        )
        if default_node is None:
            continue
        value = _static_eval(default_node, constants)
        if isinstance(value, (str, list, dict)):
            source.setdefault(key_node.value, value)
    return source


def _delegated_source_files(path: Path) -> list[Path]:
    """Find modules that explicitly bind the default translator to this facade."""
    primary = path.with_suffix(".py")
    target_name = primary.name
    delegated: list[Path] = []
    for candidate in sorted(path.parent.rglob("*.py")):
        if candidate == primary:
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "make_tool_translator" not in text or target_name not in text:
            continue
        try:
            tree = ast.parse(text, filename=str(candidate))
        except SyntaxError:
            continue
        for statement in ast.walk(tree):
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            value = statement.value
            if not isinstance(target, ast.Name) or target.id != "_":
                continue
            if not isinstance(value, ast.Call):
                continue
            if not isinstance(value.func, ast.Name):
                continue
            if value.func.id != "make_tool_translator":
                continue
            explicit_targets = {
                Path(node.value).name
                for node in ast.walk(value)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.endswith(".py")
            }
            if target_name in explicit_targets:
                delegated.append(candidate)
                break
    return delegated


def _english_source(path: Path) -> dict[str, Any]:
    """Extract Python English defaults, following facade-bound implementations."""
    py_path = path.with_suffix(".py")
    if not py_path.is_file():
        raise ValueError(f"missing Python source for i18n catalog: {py_path}")

    source = _extract_english_source(py_path)

    for delegated in _delegated_source_files(path):
        for key, value in _extract_english_source(delegated).items():
            source.setdefault(key, value)
    return source

def _value_to_text(v: Any) -> str | None:
    """Serialize a JSON value into a single translate unit.

    - str: as-is
    - list[str]: join with \\n (same convention as translate_text batch)
    - other: skip (None)
    """
    if isinstance(v, str):
        return v
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return "\n".join(v)
    return None


def _text_to_value(text: str, template: Any) -> Any:
    if isinstance(template, list):
        parts = text.split("\n")
        # If translator collapsed/expanded lines, pad/trim to template length.
        if len(parts) < len(template):
            parts = parts + list(template[len(parts) :])
        elif len(parts) > len(template):
            # Keep extras joined into last element rather than dropping content.
            head = parts[: len(template) - 1]
            tail = "\n".join(parts[len(template) - 1 :])
            parts = head + [tail]
        return parts
    return text


def _placeholders(s: str) -> set[str]:
    names = {match.group("name") for match in PRINTF_PLACEHOLDER_RE.finditer(s)}
    try:
        for _literal, field_name, _format_spec, _conversion in FORMATTER.parse(s):
            if field_name is not None and BRACE_FIELD_NAME_RE.fullmatch(field_name):
                names.add(field_name)
    except ValueError:
        names.add("<invalid-brace-format>")
    return names


def _is_missing_or_stale(
    en_val: Any,
    cur_val: Any,
    *,
    key: str | None = None,
    force: bool,
    skip_same_as_en: bool,
) -> bool:
    if force:
        return True
    if cur_val is None:
        return True
    # type mismatch counts as missing
    if type(cur_val) is not type(en_val):
        return True
    if isinstance(en_val, str) and isinstance(cur_val, str):
        if not cur_val.strip():
            return True
        if skip_same_as_en and cur_val.strip() == en_val.strip():
            return True
        return False
    if isinstance(en_val, list) and isinstance(cur_val, list):
        if key in VARIABLE_LENGTH_LIST_KEYS:
            if not cur_val or any(
                not isinstance(item, str) or not item.strip() for item in cur_val
            ):
                return True
            if skip_same_as_en and cur_val == en_val:
                return True
            return False
        if len(cur_val) != len(en_val):
            return True
        if any(not isinstance(item, str) or not item.strip() for item in cur_val):
            return True
        if skip_same_as_en and cur_val == en_val:
            return True
        return False
    return False


@dataclass
class Unit:
    tool: str
    source_path: str
    lang: str
    key: str
    en_value: Any
    text: str


def _tool_label(path: Path) -> str:
    """Return a stable diagnostic label for arbitrary tool catalog filenames."""
    stem = path.stem
    return stem[: -len("_tool")] if stem.endswith("_tool") else stem


def collect_units(
    files: Iterable[Path],
    langs: list[str],
    *,
    force: bool,
    skip_same_as_en: bool,
    only_missing: bool,
    only_existing_lang: bool = True,
) -> list[Unit]:
    units: list[Unit] = []
    for path in files:
        try:
            data = _load_json_object(path)
            en = _english_source(path)
        except Exception as e:
            print(f"[skip] {path}: {e}", file=sys.stderr)
            continue
        tool = _tool_label(path)
        present_langs = {
            k for k, v in data.items() if _is_lang_block(k, v) and k != "en"
        }
        for lang in langs:
            if lang == "en":
                continue
            if only_existing_lang and lang not in present_langs:
                # Do not create brand-new language blocks unless explicitly allowed.
                continue
            block = data.get(lang) if isinstance(data.get(lang), dict) else {}
            assert isinstance(block, dict)
            for key, en_val in en.items():
                text = _value_to_text(en_val)
                if text is None or not text.strip():
                    continue
                cur = block.get(key)
                if (
                    only_missing
                    and skip_same_as_en
                    and isinstance(en_val, str)
                    and isinstance(cur, str)
                    and cur.strip() == en_val.strip()
                    and _is_intentional_english_tool_key(tool, str(key))
                ):
                    continue
                if only_missing and not _is_missing_or_stale(
                    en_val,
                    cur,
                    key=str(key),
                    force=force,
                    skip_same_as_en=skip_same_as_en,
                ):
                    continue
                if len(text) > MAX_TEXT_LEN:
                    print(
                        f"[warn] skip too-long value {tool}/{lang}/{key} ({len(text)} chars)",
                        file=sys.stderr,
                    )
                    continue
                try:
                    rel = path.resolve().relative_to(ROOT.resolve()).as_posix()
                except Exception:
                    rel = path.as_posix()
                units.append(
                    Unit(
                        tool=tool,
                        source_path=rel,
                        lang=lang,
                        key=str(key),
                        en_value=en_val,
                        text=text,
                    )
                )
    return units


def _job_dir(tmp_dir: Path, lang: str) -> Path:
    return tmp_dir / _norm_lang(lang)


def write_extract(units: list[Unit], tmp_dir: Path) -> dict[str, Path]:
    """Write per-language extract files. Returns lang -> manifest path."""
    by_lang: dict[str, list[Unit]] = {}
    for u in units:
        by_lang.setdefault(u.lang, []).append(u)

    manifests: dict[str, Path] = {}
    for lang, items in sorted(by_lang.items()):
        d = _job_dir(tmp_dir, lang)
        d.mkdir(parents=True, exist_ok=True)
        manifest = {
            "lang": lang,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "count": len(items),
            "items": [
                {
                    "id": i,
                    "tool": u.tool,
                    "source_path": u.source_path,
                    "key": u.key,
                    "en_value": u.en_value,
                    "text": u.text,
                }
                for i, u in enumerate(items)
            ],
        }
        man_path = d / "manifest.json"
        values_path = d / "values_en.json"
        # values_en.json is a pure string array for translate_text(texts=...)
        _dump_json(man_path, manifest)
        _dump_json(values_path, [u.text for u in items])
        # human-friendly preview
        preview_path = d / "preview.tsv"
        with preview_path.open("w", encoding="utf-8", newline="\n") as f:
            f.write("id\ttool\tkey\tchars\ttext\n")
            for i, u in enumerate(items):
                one = u.text.replace("\t", "\\t").replace("\n", "\\n")
                f.write(f"{i}\t{u.tool}\t{u.key}\t{len(u.text)}\t{one}\n")
        manifests[lang] = man_path
        print(f"[extract] {lang}: {len(items)} units -> {d}")
    return manifests


def _chunk_indices(
    texts: list[str], *, max_chars: int, max_items: int
) -> list[list[int]]:
    batches: list[list[int]] = []
    cur: list[int] = []
    cur_chars = 0
    for i, t in enumerate(texts):
        add = len(t) + (1 if cur else 0)  # +1 for join newline
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


def _pip_install_commands(text: str) -> list[str]:
    """Extract copy-pasteable pip install commands from source text.

    Commands are expected to occupy the remainder of their source line. This
    preserves options, multiple requirements, extras, and version specifiers
    without attempting to parse pip's full requirement grammar.
    """
    commands: list[str] = []

    for line in text.splitlines():
        match = PIP_INSTALL_PREFIX_RE.search(line)
        if match is None:
            continue

        command = line[match.start() :].strip()
        command = command.rstrip(PIP_COMMAND_TRAILING_PUNCTUATION).rstrip()
        if command:
            commands.append(command)

    return commands


def _pip_install_protect_terms(texts: list[str]) -> list[str]:
    """Return exact pip commands and requirement names that must stay literal."""
    terms: list[str] = []
    seen: set[str] = set()

    def _add(term: str) -> None:
        if term in seen:
            return
        seen.add(term)
        terms.append(term)

    for text in texts:
        for command in _pip_install_commands(text):
            _add(command)

            tokens = command.split()[2:]
            for token in tokens:
                if token.startswith("-"):
                    continue
                match = PIP_REQUIREMENT_NAME_RE.match(token)
                if match is not None:
                    _add(match.group("name"))

    return terms


def _scope_pip_install_groups(indices: list[int], texts: list[str]) -> list[list[int]]:
    """Keep pip-install source texts isolated from unrelated batch neighbors."""
    normal: list[int] = []
    protected: list[list[int]] = []

    for index in indices:
        if _pip_install_commands(texts[index]):
            protected.append([index])
        else:
            normal.append(index)

    groups: list[list[int]] = []
    if normal:
        groups.append(normal)
    groups.extend(protected)
    return groups


def _import_translate_run_tool():
    # Prefer in-repo tool module.
    sys.path.insert(0, str(ROOT / "src"))
    from uagent.tools.translate_text_tool import run_tool  # type: ignore

    return run_tool


def translate_lang(
    lang: str,
    tmp_dir: Path,
    *,
    source_lang: str,
    provider: str,
    max_chars: int,
    max_items: int,
    sleep_s: float,
) -> Path:
    d = _job_dir(tmp_dir, lang)
    man_path = d / "manifest.json"
    values_path = d / "values_en.json"
    if not man_path.is_file() or not values_path.is_file():
        raise FileNotFoundError(f"missing extract for {lang}: run extract first ({d})")

    texts: list[str] = _load_json(values_path)  # type: ignore[assignment]
    if not isinstance(texts, list):
        raise ValueError("values_en.json must be a list")
    texts = [str(x) for x in texts]

    run_tool = _import_translate_run_tool()
    out: list[str | None] = [None] * len(texts)
    batches = _chunk_indices(texts, max_chars=max_chars, max_items=max_items)
    print(f"[translate] {lang}: {len(texts)} texts in {len(batches)} batch(es)")

    extra_terms = [
        # param / tool identifiers
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
        # common voice / model ids seen in tool JSON
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
        "ara",
        "rex",
        "sal",
        "mao",
    ]

    def _call_translate(batch_texts: list[str]) -> dict:
        payload = {
            "texts": batch_texts,
            "target_lang": lang,
            "source_lang": source_lang,
            "provider": provider,
            "protect_placeholders": True,
            "protect_terms": True,
            "extra_protect_terms": [
                *extra_terms,
                *_pip_install_protect_terms(batch_texts),
            ],
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
        batch_texts: list[str], *, depth: int = 0, rate_retries: int = 0
    ) -> list[str]:
        """Translate a batch; on line-count mismatch, split or fall back to singles."""
        if not batch_texts:
            return []
        try:
            res = _call_translate(batch_texts)
            translated = res.get("translated")
            if isinstance(translated, list) and len(translated) == len(batch_texts):
                return [str(x) for x in translated]
            raise RuntimeError(
                f"bad translated length (got {0 if not isinstance(translated, list) else len(translated)}, "
                f"expected {len(batch_texts)})"
            )
        except Exception as e:
            msg = str(e)
            if "429" in msg:
                if rate_retries < 3:
                    delay = max(float(sleep_s or 0), 10.0) * (2**rate_retries)
                    print(f"    [rate-limit] sleeping {delay:.1f}s before retry")
                    time.sleep(delay)
                    return _translate_with_fallback(
                        batch_texts, depth=depth, rate_retries=rate_retries + 1
                    )
                raise RuntimeError(
                    f"translation rate limit persisted after {rate_retries} retries: {msg}"
                ) from e
            # Single item: last resort, return original to avoid aborting whole lang.
            if len(batch_texts) == 1:
                print(f"    [warn] single-item failed, keeping EN: {msg[:160]}")
                return [batch_texts[0]]
            # Split batch in half and retry.
            mid = max(1, len(batch_texts) // 2)
            if depth >= 8:
                # too deep: per-item
                out_parts: list[str] = []
                for one in batch_texts:
                    out_parts.extend(_translate_with_fallback([one], depth=depth + 1))
                    if sleep_s > 0:
                        time.sleep(min(sleep_s, 0.05))
                return out_parts
            print(
                f"    [fallback depth={depth}] {msg[:120]} -> split {len(batch_texts)} into "
                f"{mid}+{len(batch_texts)-mid}"
            )
            left = _translate_with_fallback(batch_texts[:mid], depth=depth + 1)
            if sleep_s > 0:
                time.sleep(sleep_s)
            right = _translate_with_fallback(batch_texts[mid:], depth=depth + 1)
            return left + right

    for bi, idxs in enumerate(batches, 1):
        for scoped_idxs in _scope_pip_install_groups(idxs, texts):
            batch_texts = [texts[i] for i in scoped_idxs]
            translated = _translate_with_fallback(batch_texts)
            if len(translated) != len(batch_texts):
                raise RuntimeError(
                    f"batch {bi}: fallback produced {len(translated)} != {len(batch_texts)}"
                )
            for i, tr in zip(scoped_idxs, translated):
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

    # QC sidecar
    man = _load_json_object(man_path)
    items = man.get("items") if isinstance(man, dict) else []
    qc = []
    if isinstance(items, list):
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            en_text = str(item.get("text") or "")
            tr_text = out_list[i]
            en_ph = sorted(_placeholders(en_text))
            tr_ph = sorted(_placeholders(tr_text))
            qc.append(
                {
                    "id": i,
                    "tool": item.get("tool"),
                    "key": item.get("key"),
                    "placeholder_ok": en_ph == tr_ph,
                    "en_placeholders": en_ph,
                    "tr_placeholders": tr_ph,
                    "same_as_en": en_text.strip() == tr_text.strip(),
                    "chars_en": len(en_text),
                    "chars_tr": len(tr_text),
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
    *,
    apply: bool,
    keep_existing: bool,
) -> list[Path]:
    d = _job_dir(tmp_dir, lang)
    man = _load_json_object(d / "manifest.json")
    translated = _load_json(d / "values_translated.json")
    if not isinstance(translated, list):
        raise ValueError("values_translated.json must be a list")
    items = man.get("items")
    if not isinstance(items, list):
        raise ValueError("manifest.items missing")
    if len(items) != len(translated):
        raise ValueError(
            f"count mismatch manifest={len(items)} translated={len(translated)}"
        )

    # group by source file
    by_file: dict[str, list[tuple[dict[str, Any], str]]] = {}
    for item, tr in zip(items, translated):
        if not isinstance(item, dict):
            continue
        sp = str(item.get("source_path") or "")
        by_file.setdefault(sp, []).append((item, str(tr)))

    touched: list[Path] = []
    for sp, pairs in sorted(by_file.items()):
        path = ROOT / sp if not os.path.isabs(sp) else Path(sp)
        # source_path stored as posix relative to repo when possible
        if not path.is_file():
            alt = Path(sp)
            if alt.is_file():
                path = alt
            else:
                print(f"[merge] missing file: {sp}", file=sys.stderr)
                continue
        data = _load_json_object(path)
        block = data.get(lang)
        if not isinstance(block, dict):
            block = {}
            data[lang] = block
        changed = 0
        for item, tr_text in pairs:
            key = str(item.get("key"))
            en_value = item.get("en_value")
            new_val = _text_to_value(tr_text, en_value)
            if keep_existing and key in block and block.get(key) not in (None, ""):
                # only fill holes
                cur = block.get(key)
                if not (
                    cur is None
                    or (isinstance(cur, str) and not cur.strip())
                    or (isinstance(cur, list) and cur == en_value)
                ):
                    continue
            if block.get(key) != new_val:
                block[key] = new_val
                changed += 1
        # Stable key order follows the Python English source, then locale extras.
        en = _english_source(path)
        ordered: dict[str, Any] = {}
        for k in en.keys():
            if k in block:
                ordered[k] = block[k]
        for k, v in block.items():
            if k not in ordered:
                ordered[k] = v
        data[lang] = ordered

        if apply:
            # backup next to file
            bak = path.with_suffix(path.suffix + ".i18n.bak")
            if not bak.exists():
                bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            _dump_json(path, data)
            print(f"[merge] APPLY {path} ({lang}) changed={changed}")
        else:
            out = d / "merged_preview" / path.name
            _dump_json(out, data)
            print(f"[merge] preview {out} ({lang}) changed={changed}")
        touched.append(path)
    return touched


def _tool_files(args: argparse.Namespace) -> list[Path]:
    if args.tools_dir:
        directories = (Path(args.tools_dir),)
    else:
        directories = DEFAULT_TOOL_DIRS
    files: list[Path] = []
    for directory in directories:
        files.extend(_iter_tool_json_files(directory, args.tools_set))
    return sorted(files)


def cmd_status(args: argparse.Namespace) -> int:
    files = _tool_files(args)
    langs = args.langs_list

    require_all_locales = args.add_lang or args.require_complete
    missing_units = collect_units(
        files,
        langs,
        force=False,
        skip_same_as_en=False,
        only_missing=True,
        only_existing_lang=not require_all_locales,
    )

    same_as_en_units: list[Unit] = []
    if args.skip_same_as_en:
        review_units = collect_units(
            files,
            langs,
            force=False,
            skip_same_as_en=True,
            only_missing=True,
            only_existing_lang=not require_all_locales,
        )
        missing_ids = {(u.source_path, u.lang, u.key) for u in missing_units}
        same_as_en_units = [
            u
            for u in review_units
            if (u.source_path, u.lang, u.key) not in missing_ids
            and not _is_intentional_english_tool_key(u.tool, u.key)
        ]

    review_units = missing_units + same_as_en_units

    by_pair: dict[tuple[str, str], int] = {}
    missing_by_pair: dict[tuple[str, str], int] = {}
    missing_keys_by_tool: dict[str, set[str]] = {}
    same_keys_by_tool: dict[str, set[str]] = {}
    missing_by_lang: dict[str, int] = {}
    missing_by_tool: dict[str, int] = {}
    same_by_lang: dict[str, int] = {}
    same_by_tool_key: dict[tuple[str, str], int] = {}
    missing_by_tool_key: dict[tuple[str, str], int] = {}

    for u in review_units:
        by_pair[(u.tool, u.lang)] = by_pair.get((u.tool, u.lang), 0) + 1
    for u in missing_units:
        missing_keys_by_tool.setdefault(u.tool, set()).add(u.key)
        missing_by_pair[(u.tool, u.lang)] = (
            missing_by_pair.get((u.tool, u.lang), 0) + 1
        )
        missing_by_lang[u.lang] = missing_by_lang.get(u.lang, 0) + 1
        missing_by_tool[u.tool] = missing_by_tool.get(u.tool, 0) + 1
        tool_key = (u.tool, u.key)
        missing_by_tool_key[tool_key] = missing_by_tool_key.get(tool_key, 0) + 1
    for u in same_as_en_units:
        same_keys_by_tool.setdefault(u.tool, set()).add(u.key)
        same_by_lang[u.lang] = same_by_lang.get(u.lang, 0) + 1
        tool_key = (u.tool, u.key)
        same_by_tool_key[tool_key] = same_by_tool_key.get(tool_key, 0) + 1

    print(f"tools_scanned: {len(files)}")
    print(f"supported_locales: {len(SUPPORTED_TOOL_LOCALES)}")
    print("source_language: python default=")
    print(f"languages_scanned: {len(langs)}")
    print(f"missing_units: {len(missing_units)}")
    print(f"same_as_english_candidates: {len(same_as_en_units)}")
    print(f"review_candidates: {len(review_units)}")
    print(f"affected_tool_language_pairs: {len(by_pair)}")

    if missing_by_lang:
        print("missing_by_language:")
        for lang, n in sorted(missing_by_lang.items()):
            print(f"  {lang:8s} {n}")

    if missing_by_tool:
        print("missing_by_tool:")
        for tool, n in sorted(
            missing_by_tool.items(), key=lambda item: (-item[1], item[0])
        ):
            print(f"  {tool:40s} {n}")

    if args.show_missing_keys and missing_by_tool_key:
        print("missing_by_tool_key:")
        for (tool, key), n in sorted(
            missing_by_tool_key.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        ):
            print(f"  {tool:40s} {key:48s} {n}")

    if same_by_lang:
        print("same_as_english_by_language:")
        for lang, n in sorted(same_by_lang.items()):
            print(f"  {lang:8s} {n}")

    if missing_keys_by_tool:
        print("missing_keys_by_tool:")
        for tool, keys in sorted(missing_keys_by_tool.items()):
            print(f"  {tool:40s} {','.join(sorted(keys))}")

    if same_keys_by_tool:
        print("same_as_english_keys_by_tool:")
        for tool, keys in sorted(same_keys_by_tool.items()):
            print(f"  {tool:40s} {','.join(sorted(keys))}")

    if missing_by_pair:
        print("missing_by_tool_language:")
        for (tool, lang), n in sorted(missing_by_pair.items()):
            print(f"  {tool:40s} {lang:8s} {n}")

    if args.show_same_as_english_keys and same_by_tool_key:
        print("same_as_english_by_tool_key:")
        for (tool, key), n in sorted(
            same_by_tool_key.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        ):
            print(f"  {tool:40s} {key:48s} {n}")

    if args.show_same_as_english_units and same_as_en_units:
        print("same_as_english_units:")
        for unit in sorted(
            same_as_en_units,
            key=lambda item: (item.tool, item.lang, item.key),
        ):
            print(f"  {unit.tool:40s} {unit.lang:8s} {unit.key}")

    if by_pair:
        print("review_candidates_by_tool_language:")
        for (tool, lang), n in sorted(by_pair.items()):
            print(f"  {tool:40s} {lang:8s} {n}")

    if args.require_complete and missing_units:
        print(
            "error: tool i18n catalogs are incomplete; "
            f"{len(missing_units)} translation unit(s) are missing",
            file=sys.stderr,
        )
        return 1

    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    files = _tool_files(args)
    units = collect_units(
        files,
        args.langs_list,
        force=args.force,
        skip_same_as_en=args.skip_same_as_en,
        only_missing=not args.force,
        only_existing_lang=not args.add_lang,
    )
    if args.keys_set:
        units = [u for u in units if u.key in args.keys_set]
    if not units:
        print("[extract] nothing to do")
        return 0
    write_extract(units, Path(args.tmp_dir))
    return 0


def cmd_translate(args: argparse.Namespace) -> int:
    tmp_dir = Path(args.tmp_dir)
    for index, lang in enumerate(args.langs_list):
        translate_lang(
            lang,
            tmp_dir,
            source_lang=args.source_lang,
            provider=args.provider,
            max_chars=args.batch_chars,
            max_items=args.batch_items,
            sleep_s=args.sleep,
        )
        if args.sleep > 0 and index < len(args.langs_list) - 1:
            print(f"[translate] sleeping {args.sleep:.1f}s before next language")
            time.sleep(args.sleep)
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    tmp_dir = Path(args.tmp_dir)
    for lang in args.langs_list:
        merge_lang(
            lang,
            tmp_dir,
            apply=args.apply,
            keep_existing=args.keep_existing,
        )
    if not args.apply:
        print(
            "[merge] dry-run only (previews under tmp). Re-run with --apply to write."
        )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    rc = cmd_extract(args)
    if rc != 0:
        return rc
    rc = cmd_translate(args)
    if rc != 0:
        return rc
    return cmd_merge(args)


def _parse_langs(s: str) -> list[str]:
    parts = [_norm_lang(x) for x in (s or "").split(",") if x.strip()]
    # unique preserve order
    out: list[str] = []
    for p in parts:
        if p and p not in out:
            out.append(p)
    return out


def _parse_tools(s: str | None) -> set[str] | None:
    if not s:
        return None
    parts = [x.strip() for x in s.split(",") if x.strip()]
    return set(parts) if parts else None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Batch-translate tool JSON catalogs via tmp/")
    p.add_argument(
        "command",
        choices=["status", "extract", "translate", "merge", "run"],
        help="status|extract|translate|merge|run",
    )
    p.add_argument(
        "--tools-dir",
        default="",
        help="Directory containing tool JSON catalogs (default: tools and tools_rust)",
    )
    p.add_argument(
        "--tmp-dir",
        default=str(DEFAULT_TMP_DIR),
        help="Working directory for extract/translate artifacts",
    )
    p.add_argument(
        "--langs",
        required=False,
        default="",
        help=(
            "Comma-separated target langs (e.g. ja,de,fr). "
            "Required except status, which defaults to all 37 non-English locales."
        ),
    )
    p.add_argument(
        "--tools",
        default="",
        help="Optional comma-separated tool names (e.g. translate_text,file_grep)",
    )
    p.add_argument(
        "--keys",
        default="",
        help="Optional comma-separated translation keys (e.g. x_search_terms)",
    )
    p.add_argument(
        "--source-lang",
        default="en",
        help=(
            "Source language for translation input; must be en because "
            "Python defaults are canonical."
        ),
    )
    p.add_argument(
        "--provider",
        choices=["auto", "google", "deepl"],
        default="auto",
        help="Translation provider (default: auto)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Retranslate keys even if target already has a value",
    )
    p.add_argument(
        "--skip-same-as-en",
        action="store_true",
        default=True,
        help="Treat target==English as missing (default: true)",
    )
    p.add_argument(
        "--no-skip-same-as-en",
        action="store_false",
        dest="skip_same_as_en",
        help="Do not treat target==English as missing",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Actually write tool JSON catalogs on merge/run (otherwise preview only)",
    )
    p.add_argument(
        "--keep-existing",
        action="store_true",
        help="On merge, do not overwrite non-empty existing translations",
    )
    p.add_argument(
        "--add-lang",
        action="store_true",
        help="Allow creating a language block on files that do not have it yet",
    )
    p.add_argument(
        "--show-missing-keys",
        action="store_true",
        help="For status, print missing translation keys grouped by tool catalog",
    )
    p.add_argument(
        "--show-same-as-english-keys",
        action="store_true",
        help="For status, print target==English candidates grouped by tool and key",
    )
    p.add_argument(
        "--show-same-as-english-units",
        action="store_true",
        help="For status, print each target==English candidate as tool, locale, and key",
    )
    p.add_argument(
        "--require-complete",
        action="store_true",
        help=(
            "For status, return non-zero when any Python-source translation unit "
            "is missing; absent locale blocks are included in the check"
        ),
    )
    p.add_argument("--batch-chars", type=int, default=DEFAULT_BATCH_CHARS)
    p.add_argument("--batch-items", type=int, default=DEFAULT_BATCH_ITEMS)
    p.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Sleep seconds between translate batches",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    args.tools_set = _parse_tools(args.tools)
    args.keys_set = _parse_tools(args.keys)
    args.langs_list = _parse_langs(args.langs)
    args.source_lang = _norm_lang(args.source_lang)

    if args.source_lang != "en":
        print(
            "error: --source-lang must be en because Python defaults are canonical",
            file=sys.stderr,
        )
        return 2

    if "en" in args.langs_list:
        print(
            "error: en is the Python source language and cannot be a JSON target locale",
            file=sys.stderr,
        )
        return 2

    if args.command == "status" and not args.langs_list:
        args.langs_list = list(SUPPORTED_TARGET_LOCALES)
    elif not args.langs_list:
        print("error: --langs is required", file=sys.stderr)
        return 2

    Path(args.tmp_dir).mkdir(parents=True, exist_ok=True)

    if args.command == "status":
        return cmd_status(args)
    if args.command == "extract":
        return cmd_extract(args)
    if args.command == "translate":
        return cmd_translate(args)
    if args.command == "merge":
        return cmd_merge(args)
    if args.command == "run":
        return cmd_run(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
