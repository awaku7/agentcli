from __future__ import annotations

import json
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"


def _extract_major_strings_from_json_spec(tool_spec: dict) -> dict[str, str]:
    fn = tool_spec.get("function") or {}

    major: dict[str, str] = {}

    def put(key: str, value: str | None) -> None:
        if value is None:
            return
        major[key] = str(value)

    # top-level
    desc = fn.get("description")
    sys_prompt = fn.get("system_prompt")
    if isinstance(desc, dict):
        put("function.description.en", desc.get("en"))
        put("function.description.ja", desc.get("ja"))
    if isinstance(sys_prompt, dict):
        put("function.system_prompt.en", sys_prompt.get("en"))
        put("function.system_prompt.ja", sys_prompt.get("ja"))

    # parameters
    params = fn.get("parameters") or {}
    props = params.get("properties") or {}
    if isinstance(props, dict):
        for pname, pspec in props.items():
            if not isinstance(pspec, dict):
                continue
            pdesc = pspec.get("description")
            if isinstance(pdesc, dict):
                put(f"param.{pname}.description.en", pdesc.get("en"))
                put(f"param.{pname}.description.ja", pdesc.get("ja"))

    return major


def test_all_tool_json_specs_are_valid_json() -> None:
    for p in sorted(TOOLS_DIR.glob("*_tool.json")):
        txt = p.read_text(encoding="utf-8")
        json.loads(txt)


def test_all_tool_json_specs_have_i18n_and_differ() -> None:
    for p in sorted(TOOLS_DIR.glob("*_tool.json")):
        spec = json.loads(p.read_text(encoding="utf-8"))
        major = _extract_major_strings_from_json_spec(spec)

        # Require en/ja presence for all extracted major keys
        for k, v in major.items():
            assert v.strip() != "", f"{p.name}: empty string for {k}"

        # Require en != ja for pairs we know
        pairs = []
        if "function.description.en" in major and "function.description.ja" in major:
            pairs.append(
                (
                    "function.description",
                    major["function.description.en"],
                    major["function.description.ja"],
                )
            )
        if (
            "function.system_prompt.en" in major
            and "function.system_prompt.ja" in major
        ):
            pairs.append(
                (
                    "function.system_prompt",
                    major["function.system_prompt.en"],
                    major["function.system_prompt.ja"],
                )
            )

        for pname in (
            (spec.get("function") or {})
            .get("parameters", {})
            .get("properties", {})
            .keys()
        ):
            en_k = f"param.{pname}.description.en"
            ja_k = f"param.{pname}.description.ja"
            if en_k in major and ja_k in major:
                pairs.append((f"param.{pname}.description", major[en_k], major[ja_k]))

        for label, en, ja in pairs:
            assert en != ja, f"{p.name}: {label} is identical between en/ja"


def test_tool_json_has_matching_tool_py() -> None:
    # require that each *_tool.json has a corresponding *_tool.py
    for p in sorted(TOOLS_DIR.glob("*_tool.json")):
        py = p.with_suffix(".py")
        assert py.exists(), f"{p.name}: missing matching python file: {py.name}"
