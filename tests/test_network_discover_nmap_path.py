from __future__ import annotations


def test_find_nmap_prefers_explicit_environment(monkeypatch, tmp_path) -> None:
    from uagent.tools import network_discover_tool

    explicit = tmp_path / "custom-nmap"
    explicit.write_text("nmap", encoding="utf-8")
    monkeypatch.setenv("UAGENT_NMAP_PATH", str(explicit))
    monkeypatch.setattr(network_discover_tool, "which", lambda _name: None)

    assert network_discover_tool._find_nmap() == str(explicit)


def test_find_nmap_uses_path_when_environment_missing(monkeypatch) -> None:
    from uagent.tools import network_discover_tool

    monkeypatch.delenv("UAGENT_NMAP_PATH", raising=False)
    monkeypatch.setattr(network_discover_tool, "which", lambda name: "/usr/bin/" + name)

    assert network_discover_tool._find_nmap() == "/usr/bin/nmap"
