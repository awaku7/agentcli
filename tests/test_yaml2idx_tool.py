from __future__ import annotations

from pathlib import Path

from uagent.tools.yaml2idx_tool import run_tool


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_yaml2idx_multi_doc_and_summaries(repo_tmp_path: Path) -> None:
    src = (
        "---\n"
        "# Doc 1: Kubernetes\n"
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: api-server\n"
        "spec:\n"
        "  replicas: 3\n"
        "---\n"
        "# Doc 2: Docker Compose\n"
        "version: '3.8'\n"
        "services:\n"
        "  web:\n"
        "    image: nginx:latest\n"
        "  db:\n"
        "    image: postgres:15\n"
    )
    path = repo_tmp_path / "config.yaml"
    _write(path, src)

    out = run_tool({"path": str(path), "mode": "index"})
    assert "kind: Deployment" in out
    assert "metadata.name: api-server" in out
    assert "Docker Compose" in out
    assert "services.web.image" in out

    sec1 = run_tool({"path": str(path), "mode": "section", "section": 1})
    assert "Doc #1" in sec1 or "kind: Deployment" in sec1

    sec_key = run_tool({"path": str(path), "mode": "section", "section": 4})
    assert "api-server" in sec_key


def test_yaml2idx_missing_file(repo_tmp_path: Path) -> None:
    missing = repo_tmp_path / "no_such.yaml"
    out = run_tool({"path": str(missing), "mode": "index"})
    assert (
        "ファイルが見つかりません" in out
        or "not found" in out.lower()
        or "No such" in out
    )


def test_yaml2idx_out_of_bounds(repo_tmp_path: Path) -> None:
    path = repo_tmp_path / "simple.yaml"
    _write(path, "key: value\n")
    out = run_tool({"path": str(path), "mode": "section", "section": 99})
    assert "99" in out
