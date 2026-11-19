"""In Sandbox mode, instruction files come from the sandbox workspace."""

from uagent.runtime import mxc_backend, runtime_instructions
from uagent.runtime.execution_broker import (
    SecurityProfile,
    TrustedSandboxScope,
    execution_profile,
)


def _scope() -> TrustedSandboxScope:
    return TrustedSandboxScope(
        deployment_id="web",
        principal_id="local-user",
        project_id="project",
        scope_kind="web-room",
        scope_id="room-one",
    )


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(mxc_backend, "_local_app_data", lambda: tmp_path)
    monkeypatch.setenv("UAGENT_INSTRUCTIONS_SKIP_PROMPT", "1")
    monkeypatch.delenv("UAGENT_NON_INTERACTIVE", raising=False)
    monkeypatch.delenv("UAGENT_LOAD_INSTRUCTIONS", raising=False)
    runtime_instructions._loaded_paths.clear()

    host = tmp_path / "hostproj"
    host.mkdir()
    (host / "AGENTS.md").write_text("HOST instructions", encoding="utf-8")

    workspace = mxc_backend._workspace_for_scope(_scope())
    workspace.mkdir(parents=True)
    (workspace / "AGENTS.md").write_text("SANDBOX instructions", encoding="utf-8")
    # Above the workspace: must never be discovered in Sandbox mode.
    (tmp_path / "uagent" / "AGENTS.md").write_text(
        "ABOVE instructions", encoding="utf-8"
    )
    return host, workspace


def test_sandbox_loads_instructions_from_workspace_not_host(tmp_path, monkeypatch):
    host, _workspace = _setup(tmp_path, monkeypatch)
    with execution_profile(
        SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True, scope=_scope()
    ):
        contents = runtime_instructions.load_project_instruction_files(
            workdir=str(host)
        )
    joined = "\n".join(contents)
    assert "SANDBOX instructions" in joined
    assert "HOST instructions" not in joined
    assert "ABOVE instructions" not in joined


def test_without_sandbox_host_loading_is_unchanged(tmp_path, monkeypatch):
    host, _workspace = _setup(tmp_path, monkeypatch)
    contents = runtime_instructions.load_project_instruction_files(workdir=str(host))
    assert "HOST instructions" in "\n".join(contents)


def test_find_instruction_files_honors_stop_at(tmp_path, monkeypatch):
    _host, workspace = _setup(tmp_path, monkeypatch)
    subdir = workspace / "sub"
    subdir.mkdir()
    found = runtime_instructions._find_instruction_files(
        str(subdir), stop_at=str(workspace)
    )
    paths = [c.path for c in found]
    assert any(p.endswith("AGENTS.md") and "sandboxes" in p for p in paths)
    assert all("ABOVE" not in runtime_instructions._read_file(p) for p in paths)


def test_sandbox_includes_cannot_escape_the_workspace(tmp_path, monkeypatch):
    host, workspace = _setup(tmp_path, monkeypatch)
    secret = host / "secret.txt"
    secret.write_text("HOST SECRET", encoding="utf-8")
    (workspace / "CLAUDE.md").write_text(
        "workspace rules\n" f"@{secret}\n" "@../hostproj/secret.txt\n" "@AGENTS.md\n",
        encoding="utf-8",
    )
    with execution_profile(
        SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True, scope=_scope()
    ):
        contents = runtime_instructions.load_project_instruction_files(
            workdir=str(host)
        )
    joined = "\n".join(contents)
    assert "HOST SECRET" not in joined
    # The workspace's own files and in-workspace includes still load.
    assert "workspace rules" in joined
    assert "SANDBOX instructions" in joined


def test_sandbox_instruction_symlink_escape_is_skipped(tmp_path, monkeypatch):
    import os

    import pytest

    host, workspace = _setup(tmp_path, monkeypatch)
    agents = workspace / "AGENTS.md"
    agents.unlink()
    try:
        os.symlink(host / "AGENTS.md", agents)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with execution_profile(
        SecurityProfile.LOCAL_TRUSTED, sandbox_enabled=True, scope=_scope()
    ):
        contents = runtime_instructions.load_project_instruction_files(
            workdir=str(host)
        )
    assert "HOST instructions" not in "\n".join(contents)
