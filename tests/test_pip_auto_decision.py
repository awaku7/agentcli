from uagent import _pip_auto


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
