"""Tool manifest: lazy plugin registration from a cached spec record (P0-2)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from uagent.tools import _manifest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"


def _spec(name: str, level: int = 1, **extra) -> dict:
    return {
        "type": "function",
        "tool_level": level,
        "function": {"name": name, "description": f"{name} tool", "parameters": {}},
        **extra,
    }


def _module(**attrs) -> SimpleNamespace:
    attrs.setdefault("run_tool", lambda args: "ok")
    return SimpleNamespace(**attrs)


# ── classification ──────────────────────────────────────────────────────


def test_hidden_tool_is_lazy_with_json_copy_of_specs() -> None:
    spec = _spec("alpha")
    entry = _manifest.classify_module(_module(TOOL_SPEC=spec), frozenset())
    assert entry == {"kind": "lazy", "specs": {"TOOL_SPEC": spec}}
    assert entry["specs"]["TOOL_SPEC"] is not spec


def test_helper_module_without_spec_or_commands_is_skipped() -> None:
    helper = SimpleNamespace(VALUE=1)
    assert _manifest.classify_module(helper, frozenset()) == {"kind": "skip"}


@pytest.mark.parametrize(
    "attrs",
    [
        {"TOOL_SPEC": _spec("a", level=0)},  # visible at startup
        {"TOOL_SPEC": {"type": "function", "function": {"name": "a"}}},  # default 0
        {"TOOL_SPEC": _spec("a"), "TOOL_SPEC_2": _spec("b", level=0)},
        {"TOOL_SPEC": _spec("a"), "CMD_SPEC": {"command": "x", "handler": print}},
        {"TOOL_SPEC": _spec("a"), "is_loadable": lambda: True},
        {"TOOL_SPEC": _spec("a"), "LOAD_DISABLED_REASON": "Windows only"},
        {"TOOL_SPEC": _spec("a"), "LAZY_LOAD": True},
        {"TOOL_SPEC": _spec("a", x_single_load_seq=-1)},
        {"TOOL_SPEC": _spec("a", default=("tuple", "is", "not", "json"))},
        {"TOOL_SPEC": _spec("a", callback=print)},
        {"TOOL_SPEC": _spec("excluded")},
        {"CMD_SPECS": [{"command": "x", "handler": print}]},  # commands only
    ],
)
def test_modules_that_need_their_code_stay_eager(attrs: dict) -> None:
    mod = _module(**attrs)
    if "TOOL_SPEC" not in attrs:
        del mod.run_tool
    assert _manifest.classify_module(mod, frozenset({"excluded"})) is None


def test_tool_names_of_lists_every_spec_name() -> None:
    entry = _manifest.classify_module(
        _module(TOOL_SPEC=_spec("a"), TOOL_SPEC_3=_spec("c", level=-1)), frozenset()
    )
    assert _manifest.tool_names_of(entry) == ["a", "c"]


# ── fingerprint and storage ─────────────────────────────────────────────


def _make_pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "a_tool.py").write_text("X = 1\n", encoding="utf-8")
    (pkg / "a_tool.json").write_text("{}", encoding="utf-8")
    (pkg / "sub" / "helper.py").write_text("Y = 1\n", encoding="utf-8")
    return pkg


def test_fingerprint_changes_with_files_locale_and_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = _make_pkg(tmp_path)
    base = _manifest.compute_fingerprint(str(pkg), "en")
    assert _manifest.compute_fingerprint(str(pkg), "en") == base
    assert _manifest.compute_fingerprint(str(pkg), "ja") != base

    monkeypatch.setenv("UAGENT_ENABLE_SEMANTIC_SEARCH", "1")
    with_env = _manifest.compute_fingerprint(str(pkg), "en")
    assert with_env != base

    # Per-process values do not invalidate the cache.
    monkeypatch.setenv("UAGENT_A2A_PORT", "9999")
    assert _manifest.compute_fingerprint(str(pkg), "en") == with_env

    (pkg / "sub" / "helper.py").write_text("Y = 22\n", encoding="utf-8")
    assert _manifest.compute_fingerprint(str(pkg), "en") != with_env


def test_manifest_round_trip_and_rejections(tmp_path: Path) -> None:
    path = tmp_path / "cache" / "m.json"
    entries = {"a_tool": {"kind": "lazy", "specs": {"TOOL_SPEC": _spec("a")}}}
    _manifest.save_manifest(path, "fp1", entries)

    assert _manifest.load_manifest(path, "fp1") == entries
    assert _manifest.load_manifest(path, "other") is None
    assert _manifest.load_manifest(tmp_path / "missing.json", "fp1") is None

    path.write_text("{not json", encoding="utf-8")
    assert _manifest.load_manifest(path, "fp1") is None

    data = {"format": _manifest.MANIFEST_FORMAT + 1, "fingerprint": "fp1"}
    path.write_text(json.dumps(data), encoding="utf-8")
    assert _manifest.load_manifest(path, "fp1") is None


def test_manifest_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UAGENT_TOOL_MANIFEST", "off")
    assert _manifest.manifest_enabled() is False
    monkeypatch.setenv("UAGENT_TOOL_MANIFEST", "on")
    assert _manifest.manifest_enabled() is True


# ── module view ─────────────────────────────────────────────────────────


def test_view_answers_specs_and_known_absent_attrs_without_import() -> None:
    name = "uagent.tools.__does_not_exist_tool"
    view = _manifest.ManifestModuleView(name, {"TOOL_SPEC": _spec("a")})

    assert view.TOOL_SPEC["function"]["name"] == "a"
    assert getattr(view, "TOOL_SPEC_2", None) is None
    assert getattr(view, "LOAD_DISABLED_REASON", "") == ""
    assert getattr(view, "is_loadable", None) is None
    assert dir(view) == ["TOOL_SPEC"]
    assert name not in sys.modules

    # Anything else needs the real module.
    with pytest.raises(ModuleNotFoundError):
        getattr(view, "run_tool")


# ── end to end: build the cache, then load from it ──────────────────────

_E2E_SCRIPT = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import uagent.tools as T
from uagent.tools._tool_load_util import _find_tool_modules, enable_single_tool

T._ensure_loaded()
lazy = sorted(n for n, r in T._RUNNERS.items() if isinstance(r, T._LazyRunner))
out = {
    "lazy": lazy,
    "visible": sorted(s["function"]["name"] for s in T.TOOL_SPECS),
    "runners": sorted(T._RUNNERS),
}
if lazy:
    mods = dict(_find_tool_modules())
    out["date_calc_is_view"] = type(mods.get("date_calc_tool")).__name__
    out["date_calc_imported_before_run"] = "uagent.tools.date_calc_tool" in sys.modules
    catalog = T.get_tool_catalog(query="date_calc")
    out["catalog_has_date_calc"] = any(r["name"] == "date_calc" for r in catalog)
    out["date_calc_imported_after_catalog"] = (
        "uagent.tools.date_calc_tool" in sys.modules
    )
    result = T.run_tool("date_calc", {"base_date": "2026-01-01", "days": 1})
    out["run_result_ok"] = "2026-01-02" in str(result)
    out["runner_resolved"] = not isinstance(T._RUNNERS["date_calc"], T._LazyRunner)
    out["enable_single_tool"] = enable_single_tool("geodesic_distance")
    out["geodesic_visible"] = any(
        s["function"]["name"] == "geodesic_distance" for s in T.TOOL_SPECS
    )
print("E2E=" + json.dumps(out))
"""


def _run_e2e(state_dir: Path, **env_overrides: str) -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "UAGENT_STATE_DIR": str(state_dir),
            "UAGENT_AUTO_INSTALL": "off",
            "UAGENT_TOOLS_WARMUP": "0",
            "PYTHONIOENCODING": "utf-8",
            **env_overrides,
        }
    )
    proc = subprocess.run(
        [sys.executable, "-c", _E2E_SCRIPT, str(SRC_DIR)],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("E2E="):
            return json.loads(line[4:])
    raise AssertionError(proc.stderr[-3000:])


def test_second_process_registers_from_manifest_and_imports_on_use(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    first = _run_e2e(state)
    assert first["lazy"] == []  # no cache yet: every plugin imported
    assert list((state / "cache" / "tool_manifest").glob("*.json"))

    second = _run_e2e(state)
    # Same registrations as the eager load, mostly backed by lazy runners.
    assert second["runners"] == first["runners"]
    assert second["visible"] == first["visible"]
    assert "date_calc" in second["lazy"]

    assert second["date_calc_is_view"] == "ManifestModuleView"
    assert second["date_calc_imported_before_run"] is False
    assert second["catalog_has_date_calc"] is True
    assert second["date_calc_imported_after_catalog"] is False
    assert second["run_result_ok"] is True
    assert second["runner_resolved"] is True
    assert second["enable_single_tool"] is True
    assert second["geodesic_visible"] is True


def test_kill_switch_keeps_the_eager_path(tmp_path: Path) -> None:
    state = tmp_path / "state"
    _run_e2e(state)
    result = _run_e2e(state, UAGENT_TOOL_MANIFEST="off")
    assert result["lazy"] == []
