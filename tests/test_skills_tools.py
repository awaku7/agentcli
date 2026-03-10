from __future__ import annotations

import json
from pathlib import Path

import pytest


def _loads(s: str):
    return json.loads(s)


def _write_skill(skill_dir: Path, *, body: str = "# Skill\n") -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_name = skill_dir.name
    skill_md = (
        "---\n"
        f"name: {skill_name}\n"
        "description: test skill\n"
        "license: MIT\n"
        "---\n\n"
        f"{body}"
    )
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")


def test_skills_validate_ok(repo_tmp_path: Path) -> None:
    from uagent.tools.skills_validate_tool import run_tool

    skill_dir = repo_tmp_path / "demo-skill"
    _write_skill(skill_dir)

    out = run_tool({"skill_dir": str(skill_dir), "strict": False})
    obj = _loads(out)
    assert obj["ok"] is True
    assert obj["errors"] == []


def test_skills_validate_missing_skill_md(repo_tmp_path: Path) -> None:
    from uagent.tools.skills_validate_tool import run_tool

    skill_dir = repo_tmp_path / "no-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)

    out = run_tool({"skill_dir": str(skill_dir), "strict": False})
    obj = _loads(out)
    assert obj["ok"] is False
    assert any("SKILL.md not found" in e for e in obj["errors"])


def test_skills_load_returns_frontmatter_and_body(repo_tmp_path: Path) -> None:
    from uagent.tools.skills_load_tool import run_tool

    skill_dir = repo_tmp_path / "load-skill"
    _write_skill(skill_dir, body="## Body section\n")

    out = run_tool({"skill_dir": str(skill_dir)})
    obj = _loads(out)
    assert obj["path"] == str(skill_dir)
    assert obj["frontmatter"]["name"] == "load-skill"
    assert "Body section" in obj["body_markdown"]


def test_skills_read_file_ok(repo_tmp_path: Path) -> None:
    from uagent.tools.skills_read_file_tool import run_tool

    skill_dir = repo_tmp_path / "read-skill"
    _write_skill(skill_dir)
    ref = skill_dir / "references" / "REFERENCE.md"
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text("hello", encoding="utf-8")

    out = run_tool(
        {
            "skill_dir": str(skill_dir),
            "relative_path": "references/REFERENCE.md",
            "max_bytes": 1024,
        }
    )
    obj = _loads(out)
    assert obj["ok"] is True
    assert obj["content"] == "hello"


def test_skills_read_file_not_found(repo_tmp_path: Path) -> None:
    from uagent.tools.skills_read_file_tool import run_tool

    skill_dir = repo_tmp_path / "missing-ref-skill"
    _write_skill(skill_dir)

    out = run_tool(
        {
            "skill_dir": str(skill_dir),
            "relative_path": "references/not_found.md",
            "max_bytes": 1024,
        }
    )
    obj = _loads(out)
    assert obj["ok"] is False
    assert "File not found" in obj["error"]


def test_skills_read_file_rejects_path_traversal(repo_tmp_path: Path) -> None:
    from uagent.tools.skills_read_file_tool import run_tool

    skill_dir = repo_tmp_path / "traversal-skill"
    _write_skill(skill_dir)

    with pytest.raises(ValueError):
        run_tool(
            {
                "skill_dir": str(skill_dir),
                "relative_path": "../outside.txt",
                "max_bytes": 1024,
            }
        )


def test_skills_list_filters_invalid_when_requested(repo_tmp_path: Path) -> None:
    from uagent.tools.skills_list_tool import run_tool

    valid = repo_tmp_path / "valid-skill"
    _write_skill(valid)

    invalid = repo_tmp_path / "invalid-skill"
    invalid.mkdir(parents=True, exist_ok=True)
    (invalid / "SKILL.md").write_text("not-a-frontmatter", encoding="utf-8")

    out_all = run_tool(
        {
            "root_dir": str(repo_tmp_path),
            "recursive": True,
            "include_invalid": True,
            "strict": False,
        }
    )
    obj_all = _loads(out_all)
    assert len(obj_all) == 2

    out_valid_only = run_tool(
        {
            "root_dir": str(repo_tmp_path),
            "recursive": True,
            "include_invalid": False,
            "strict": False,
        }
    )
    obj_valid_only = _loads(out_valid_only)
    assert len(obj_valid_only) == 1
    assert obj_valid_only[0]["name"] == "valid-skill"


def test_skills_list_non_recursive(repo_tmp_path: Path) -> None:
    from uagent.tools.skills_list_tool import run_tool

    top = repo_tmp_path / "top-skill"
    _write_skill(top)

    nested = repo_tmp_path / "nested" / "child-skill"
    _write_skill(nested)

    out = run_tool(
        {
            "root_dir": str(repo_tmp_path),
            "recursive": False,
            "include_invalid": True,
            "strict": False,
        }
    )
    obj = _loads(out)
    names = {x["name"] for x in obj}
    assert "top-skill" in names
    assert "child-skill" not in names
