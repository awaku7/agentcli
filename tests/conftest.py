from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "src" / "uagent" / "tools"
TEST_TMP_ROOT = REPO_ROOT / "tests" / "_tmp"


def iter_tool_module_paths() -> Iterable[Path]:
    # Only python files directly under tools/ (not subpackages)
    for p in sorted(TOOLS_DIR.glob("*.py")):
        if p.name == "__init__.py":
            continue
        yield p


def module_name_from_path(p: Path) -> str:
    # src layout
    return f"uagent.tools.{p.stem}"


@pytest.fixture(scope="session")
def tool_modules() -> list[object]:
    import importlib

    mods: list[object] = []
    for p in iter_tool_module_paths():
        modname = module_name_from_path(p)
        mods.append(importlib.import_module(modname))
    return mods


@pytest.fixture(scope="session")
def tool_modules_with_spec(tool_modules: list[object]) -> list[object]:
    return [m for m in tool_modules if isinstance(getattr(m, "TOOL_SPEC", None), dict)]


@pytest.fixture()
def repo_tmp_path(request: pytest.FixtureRequest) -> Path:
    """Temporary directory under repo workdir.

    Many tools enforce "path must be under workdir". pytest's built-in tmp_path
    points to OS temp (outside repo), so we create a per-test dir under tests/_tmp.
    """

    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    safe_name = request.node.name.replace("/", "_").replace("\\", "_")
    p = TEST_TMP_ROOT / safe_name

    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=False)

    yield p

    # Best-effort cleanup
    try:
        shutil.rmtree(p)
    except OSError:
        pass
