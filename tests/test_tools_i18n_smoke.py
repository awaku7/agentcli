from __future__ import annotations

import importlib
import os
from typing import Iterable

import pytest


def _iter_tool_modules_with_json() -> Iterable[str]:
    """Yield tool module basenames under uagent.tools that:

    - have a sibling JSON (<module>.py + <module>.json)
    - expose TOOL_SPEC as a dict

    Notes:
    - src/uagent/tools also ships helper JSON files (e.g. safe_file_ops.json) that
      are not tool modules. We intentionally exclude those.
    """

    tools_dir = os.path.join(os.path.dirname(__file__), "..", "src", "uagent", "tools")
    tools_dir = os.path.abspath(tools_dir)

    for name in os.listdir(tools_dir):
        if not name.endswith(".json"):
            continue
        if name == "__init__.json":
            continue

        base = name[: -len(".json")]
        py = os.path.join(tools_dir, f"{base}.py")
        if not os.path.exists(py):
            continue

        modname = f"uagent.tools.{base}"
        try:
            importlib.invalidate_caches()
            mod = importlib.import_module(modname)
        except Exception:
            # Import failure is a separate problem; keep it visible in tests by
            # letting the main test attempt the import and fail there.
            yield base
            continue

        spec = getattr(mod, "TOOL_SPEC", None)
        if isinstance(spec, dict):
            yield base


def _extract_major_strings(tool_spec: dict) -> dict[str, str]:
    """Extract major user-facing strings that must be localized."""

    fn = tool_spec.get("function") or {}

    out: dict[str, str] = {}

    for k in ("description", "system_prompt"):
        v = fn.get(k)
        if isinstance(v, str):
            out[f"function.{k}"] = v

    params = (fn.get("parameters") or {}).get("properties") or {}
    if isinstance(params, dict):
        for pname, pinfo in params.items():
            if not isinstance(pinfo, dict):
                continue
            d = pinfo.get("description")
            if isinstance(d, str):
                out[f"param.{pname}.description"] = d

    return out


@pytest.mark.parametrize(
    "tool_module_basename", sorted(set(_iter_tool_modules_with_json()))
)
def test_tool_spec_all_major_strings_differ_between_en_and_ja(
    monkeypatch: pytest.MonkeyPatch, tool_module_basename: str
) -> None:
    """I18N strict test for tools.

    Requirement (strict): for tools that ship a sibling JSON and expose TOOL_SPEC,
    all major user-facing strings must differ between en and ja.

    This is intentionally strict so it forces filling ja entries in the JSON instead
    of silently falling back to en/default.
    """

    modname = f"uagent.tools.{tool_module_basename}"

    def _load_major_strings_for(lang: str) -> dict[str, str]:
        monkeypatch.setenv("UAGENT_LANG", lang)
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LANG", raising=False)

        importlib.invalidate_caches()
        if modname in importlib.sys.modules:
            del importlib.sys.modules[modname]

        mod = importlib.import_module(modname)
        spec = getattr(mod, "TOOL_SPEC", None)
        assert isinstance(spec, dict)

        strings = _extract_major_strings(spec)
        assert strings, "expected at least one user-facing string in TOOL_SPEC"

        for k, v in strings.items():
            assert isinstance(v, str) and v.strip(), f"empty string: {k}"

        return strings

    en = _load_major_strings_for("en")
    ja = _load_major_strings_for("ja")

    assert set(en.keys()) == set(ja.keys()), (
        tool_module_basename,
        en.keys(),
        ja.keys(),
    )

    same_keys = [k for k in sorted(en.keys()) if en[k] == ja[k]]
    assert not same_keys, (
        f"I18N mismatch (strings identical between en and ja): {tool_module_basename}",
        same_keys,
        {k: en[k] for k in same_keys},
    )
