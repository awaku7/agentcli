import json
from pathlib import Path
from uagent.tools.zip_ops_tool import run_tool


def _parse(res: str) -> dict:
    return json.loads(res)


def test_zip_ops_relative_to_and_strip_components(repo_tmp_path: Path) -> None:
    src_dir = repo_tmp_path / "app" / "v1"
    src_dir.mkdir(parents=True)
    (src_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    (src_dir / "readme.txt").write_text("test readme", encoding="utf-8")

    zip_rel = (repo_tmp_path / "pkg.zip").relative_to(Path.cwd()).as_posix()
    src_rel = src_dir.relative_to(Path.cwd()).as_posix()
    rel_base = (repo_tmp_path / "app").relative_to(Path.cwd()).as_posix()

    # create with relative_to
    out = run_tool(
        {
            "action": "create",
            "zip_path": zip_rel,
            "sources": [src_rel],
            "relative_to": rel_base,
        }
    )
    data = _parse(out)
    assert data["ok"] is True
    assert set(data["added"]) == {"v1/main.py", "v1/readme.txt"}

    # view file without extracting
    view_out = run_tool(
        {
            "action": "view",
            "zip_path": zip_rel,
            "target_file": "v1/readme.txt",
        }
    )
    view_data = _parse(view_out)
    assert view_data["ok"] is True
    assert view_data["content"] == "test readme"

    # extract with strip_components=1
    out_dir = repo_tmp_path / "extracted"
    out_rel = out_dir.relative_to(Path.cwd()).as_posix()
    ext_out = run_tool(
        {
            "action": "extract",
            "zip_path": zip_rel,
            "dest_dir": out_rel,
            "strip_components": 1,
        }
    )
    ext_data = _parse(ext_out)
    assert ext_data["ok"] is True
    assert (out_dir / "main.py").exists()
    assert (out_dir / "readme.txt").exists()
    assert (out_dir / "main.py").read_text(encoding="utf-8") == "print('hello')"


def test_tar_gz_lifecycle_and_extract_files(repo_tmp_path: Path) -> None:
    src_dir = repo_tmp_path / "tardir"
    src_dir.mkdir(parents=True)
    (src_dir / "a.txt").write_text("aaa", encoding="utf-8")
    (src_dir / "b.log").write_text("bbb", encoding="utf-8")
    (src_dir / "c.txt").write_text("ccc", encoding="utf-8")

    tar_rel = (repo_tmp_path / "archive.tar.gz").relative_to(Path.cwd()).as_posix()
    src_rel = src_dir.relative_to(Path.cwd()).as_posix()

    # create tar.gz
    out = run_tool(
        {
            "action": "create",
            "zip_path": tar_rel,
            "sources": [src_rel],
            "relative_to": src_rel,
        }
    )
    data = _parse(out)
    assert data["ok"] is True
    assert data["format"] == "tar.gz"
    assert set(data["added"]) == {"a.txt", "b.log", "c.txt"}

    # list
    list_out = run_tool(
        {
            "action": "list",
            "zip_path": tar_rel,
        }
    )
    list_data = _parse(list_out)
    assert list_data["ok"] is True
    assert list_data["format"] == "tar.gz"
    assert len(list_data["entries"]) == 3

    # selective extract
    out_dir = repo_tmp_path / "tar_out"
    out_rel = out_dir.relative_to(Path.cwd()).as_posix()
    ext_out = run_tool(
        {
            "action": "extract",
            "zip_path": tar_rel,
            "dest_dir": out_rel,
            "extract_files": ["*.txt"],
        }
    )
    ext_data = _parse(ext_out)
    assert ext_data["ok"] is True
    assert (out_dir / "a.txt").exists()
    assert (out_dir / "c.txt").exists()
    assert not (out_dir / "b.log").exists()


def test_view_tar_and_limits(repo_tmp_path: Path) -> None:
    src_dir = repo_tmp_path / "viewdir"
    src_dir.mkdir(parents=True)
    (src_dir / "large.txt").write_text("0123456789" * 10, encoding="utf-8")

    tar_rel = (repo_tmp_path / "view.tar").relative_to(Path.cwd()).as_posix()
    src_rel = src_dir.relative_to(Path.cwd()).as_posix()

    run_tool(
        {
            "action": "create",
            "zip_path": tar_rel,
            "sources": [src_rel],
            "relative_to": src_rel,
        }
    )

    # view with max_bytes
    v_out = run_tool(
        {
            "action": "view",
            "zip_path": tar_rel,
            "target_file": "large.txt",
            "max_bytes": 10,
        }
    )
    v_data = _parse(v_out)
    assert v_data["ok"] is True
    assert v_data["content"] == "0123456789"
    assert v_data["truncated"] is True


def test_view_missing_target(repo_tmp_path: Path) -> None:
    src_dir = repo_tmp_path / "s"
    src_dir.mkdir()
    (src_dir / "f.txt").write_text("hello", encoding="utf-8")

    tar_rel = (repo_tmp_path / "sample.zip").relative_to(Path.cwd()).as_posix()
    src_rel = src_dir.relative_to(Path.cwd()).as_posix()
    run_tool(
        {
            "action": "create",
            "zip_path": tar_rel,
            "sources": [src_rel],
        }
    )
    res = run_tool(
        {
            "action": "view",
            "zip_path": tar_rel,
        }
    )
    data = _parse(res)
    assert data["ok"] is False
    assert "target_file" in data["error"]
