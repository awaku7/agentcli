from __future__ import annotations

import os
from pathlib import Path

import pytest


def _valid_frontmatter(name: str) -> dict:
    return {
        "name": name,
        "description": "desc",
        "license": "MIT",
    }


def test_split_frontmatter_ok_with_leading_blank_lines() -> None:
    from uagent.tools.agent_skills_shared import split_frontmatter

    text = "\n\n---\nname: demo-skill\ndescription: x\n---\n# Body\n"
    fm, body = split_frontmatter(text)

    assert "name: demo-skill" in fm
    assert body == "# Body\n"


def test_split_frontmatter_missing_start_raises() -> None:
    from uagent.tools.agent_skills_shared import split_frontmatter

    with pytest.raises(ValueError):
        split_frontmatter("name: x\n---\nbody\n")


def test_split_frontmatter_missing_end_raises() -> None:
    from uagent.tools.agent_skills_shared import split_frontmatter

    with pytest.raises(ValueError):
        split_frontmatter("---\nname: x\n")


def test_parse_frontmatter_yaml_rejects_non_mapping() -> None:
    from uagent.tools.agent_skills_shared import parse_frontmatter_yaml

    with pytest.raises(ValueError):
        parse_frontmatter_yaml("- a\n- b\n")


def test_parse_frontmatter_yaml_rejects_invalid_yaml() -> None:
    from uagent.tools.agent_skills_shared import parse_frontmatter_yaml

    with pytest.raises(ValueError):
        parse_frontmatter_yaml("name: [unterminated\n")


def test_read_skill_md_and_load_skill_doc(repo_tmp_path: Path) -> None:
    from uagent.tools.agent_skills_shared import load_skill_doc, read_skill_md

    skill_dir = repo_tmp_path / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: demo\nlicense: MIT\n---\n\n# Body\n",
        encoding="utf-8",
    )

    text = read_skill_md(str(skill_dir))
    assert "name: demo-skill" in text

    doc = load_skill_doc(str(skill_dir))
    assert doc.path == str(skill_dir)
    assert doc.frontmatter["name"] == "demo-skill"
    assert "# Body" in doc.body_markdown


def test_read_skill_md_too_large_raises(repo_tmp_path: Path) -> None:
    from uagent.tools.agent_skills_shared import read_skill_md

    skill_dir = repo_tmp_path / "big-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("x" * 20, encoding="utf-8")

    with pytest.raises(ValueError):
        read_skill_md(str(skill_dir), max_bytes=10)


def test_validate_skill_frontmatter_ok(repo_tmp_path: Path) -> None:
    from uagent.tools.agent_skills_shared import validate_skill_frontmatter

    skill_dir = repo_tmp_path / "good-skill"
    skill_dir.mkdir(parents=True)

    ok, errors, warnings = validate_skill_frontmatter(
        str(skill_dir), _valid_frontmatter("good-skill"), strict=False
    )
    assert ok is True
    assert errors == []
    assert warnings == []


def test_validate_skill_frontmatter_catches_name_mismatch(repo_tmp_path: Path) -> None:
    from uagent.tools.agent_skills_shared import validate_skill_frontmatter

    skill_dir = repo_tmp_path / "dir-name"
    skill_dir.mkdir(parents=True)

    ok, errors, _warnings = validate_skill_frontmatter(
        str(skill_dir), _valid_frontmatter("other-name"), strict=False
    )
    assert ok is False
    assert len(errors) >= 1


def test_validate_skill_frontmatter_optional_type_errors(repo_tmp_path: Path) -> None:
    from uagent.tools.agent_skills_shared import validate_skill_frontmatter

    skill_dir = repo_tmp_path / "typed-skill"
    skill_dir.mkdir(parents=True)

    fm = _valid_frontmatter("typed-skill")
    fm["license"] = 123
    fm["compatibility"] = 456
    fm["metadata"] = "bad"
    fm["allowed-tools"] = ["x"]

    ok, errors, _warnings = validate_skill_frontmatter(str(skill_dir), fm, strict=False)
    assert ok is False
    assert len(errors) >= 4


def test_safe_resolve_skill_relative_path_ok(repo_tmp_path: Path) -> None:
    from uagent.tools.agent_skills_shared import safe_resolve_skill_relative_path

    skill_dir = repo_tmp_path / "safe-skill"
    skill_dir.mkdir(parents=True)

    p = safe_resolve_skill_relative_path(str(skill_dir), "references/REFERENCE.md")

    assert p.startswith(str(skill_dir))
    assert p.endswith(os.path.join("references", "REFERENCE.md"))


def test_safe_resolve_skill_relative_path_rejects_dotdot(repo_tmp_path: Path) -> None:
    from uagent.tools.agent_skills_shared import safe_resolve_skill_relative_path

    skill_dir = repo_tmp_path / "safe-skill2"
    skill_dir.mkdir(parents=True)

    with pytest.raises(ValueError):
        safe_resolve_skill_relative_path(str(skill_dir), "../outside.txt")


def test_safe_resolve_skill_relative_path_rejects_root_target(
    repo_tmp_path: Path,
) -> None:
    from uagent.tools.agent_skills_shared import safe_resolve_skill_relative_path

    skill_dir = repo_tmp_path / "safe-skill3"
    skill_dir.mkdir(parents=True)

    with pytest.raises(ValueError):
        safe_resolve_skill_relative_path(str(skill_dir), ".")


def test_get_default_skill_roots_uses_env_and_dedup(
    monkeypatch, repo_tmp_path: Path
) -> None:
    from uagent.tools.agent_skills_shared import get_default_skill_roots

    root_a = repo_tmp_path / "a"
    root_b = repo_tmp_path / "b"
    root_a.mkdir(parents=True)
    root_b.mkdir(parents=True)

    sep = os.pathsep
    monkeypatch.setenv("UAGENT_SKILLS_DIRS", f"{root_a}{sep}{root_b}{sep}{root_a}")

    roots = get_default_skill_roots(cwd=str(repo_tmp_path))

    assert str(root_a) in roots
    assert str(root_b) in roots
    assert roots.count(str(root_a)) == 1
    assert any(p.endswith("skills") for p in roots)
