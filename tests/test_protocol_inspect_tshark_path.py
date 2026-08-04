from __future__ import annotations


def test_find_tshark_prefers_explicit_environment(monkeypatch, tmp_path) -> None:
    from uagent.tools import protocol_inspect_tool

    explicit = tmp_path / "tshark.exe"
    explicit.write_text("tshark", encoding="utf-8")
    monkeypatch.setenv("UAGENT_TSHARK_PATH", str(explicit))
    monkeypatch.setattr(protocol_inspect_tool, "which", lambda _name: None)

    assert protocol_inspect_tool._find_tshark() == str(explicit)


def test_find_tshark_uses_path_when_environment_missing(monkeypatch) -> None:
    from uagent.tools import protocol_inspect_tool

    monkeypatch.delenv("UAGENT_TSHARK_PATH", raising=False)
    monkeypatch.setattr(protocol_inspect_tool, "which", lambda name: "/usr/bin/" + name)

    assert protocol_inspect_tool._find_tshark() == "/usr/bin/tshark"
