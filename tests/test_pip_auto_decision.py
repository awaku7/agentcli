from uagent import _pip_auto
import builtins
import importlib.metadata
from types import ModuleType


def test_version_satisfies_compound_specifier():
    assert _pip_auto._version_satisfies("0.3.23", ">=0.3.23,<0.4")
    assert _pip_auto._version_satisfies("0.3.99", ">=0.3.23,<0.4")
    assert not _pip_auto._version_satisfies("0.4.0", ">=0.3.23,<0.4")


def test_may_install_checks_package_name_not_display_name(monkeypatch):
    monkeypatch.setenv("UAGENT_AUTO_INSTALL", "allow")

    assert _pip_auto._may_install("laya", display_name="Laya Decision Provider")
    assert not _pip_auto._may_install(
        "definitely-not-allowlisted",
        display_name="Friendly Name",
    )


def test_install_with_status_checks_distribution_base_name_for_extras(monkeypatch):
    real_import = builtins.__import__
    imported: list[str] = []
    versions: list[str] = []

    def fake_import(name, *args, **kwargs):
        if name == "markitdown_test_module":
            imported.append(name)
            return ModuleType(name)
        return real_import(name, *args, **kwargs)

    def fake_version(name: str) -> str:
        versions.append(name)
        return "0.1.9"

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(importlib.metadata, "version", fake_version)

    assert _pip_auto.install_with_status(
        "markitdown[all]",
        "markitdown_test_module",
        version_spec=">=0.1.9",
    )
    assert imported == ["markitdown_test_module"]
    assert versions == ["markitdown"]
