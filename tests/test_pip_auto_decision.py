from __future__ import annotations

import importlib.metadata

from uagent import _pip_auto


def test_laya_is_allowed_for_shared_auto_install():
    assert _pip_auto._install_allowed("laya") is True


def test_compound_version_spec_rejects_out_of_range_install(monkeypatch):
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "0.4.0")
    monkeypatch.setattr(_pip_auto, "_may_install", lambda _label: False)

    assert (
        _pip_auto.install_with_status(
            "laya",
            "json",
            version_spec=">=0.3.23,<0.4",
        )
        is False
    )


def test_compound_version_spec_accepts_supported_install(monkeypatch):
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "0.3.23")

    assert (
        _pip_auto.install_with_status(
            "laya",
            "json",
            version_spec=">=0.3.23,<0.4",
        )
        is True
    )
