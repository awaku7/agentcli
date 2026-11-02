"""Verify that UAG distributions contain the execution library without its Web host."""

from email.parser import Parser
from pathlib import Path
from tarfile import open as open_tar
from zipfile import ZipFile


def assert_no_web_payload(names):
    for name in names:
        normalized = name.replace("\\", "/")
        assert not any(
            marker in normalized
            for marker in (
                "uagent/web.py",
                "uagent/web_impl/",
                "uagent/static/",
                "uagent/templates/",
                "/frontend/",
            )
        ), name


wheel = next(Path("dist").glob("uag-*.whl"))
with ZipFile(wheel) as archive:
    names = archive.namelist()
    assert_no_web_payload(names)
    entry_points = archive.read(
        next(name for name in names if name.endswith("/entry_points.txt"))
    ).decode()
    for entry in (
        "uag = uagent.cli_entry:main",
        "uaga = uagent.a2a.server:main",
        "uagg = uagent.gui:main",
    ):
        assert entry in entry_points
    assert "uagw =" not in entry_points
    metadata = Parser().parsestr(
        archive.read(
            next(name for name in names if name.endswith("/METADATA"))
        ).decode()
    )
    assert not any(
        dependency.startswith("uag-web")
        for dependency in metadata.get_all("Requires-Dist", [])
    )

with open_tar(next(Path("dist").glob("uag-*.tar.gz"))) as archive:
    assert_no_web_payload(archive.getnames())
print("Core wheel/sdist exclude Web payload and preserve CLI/GUI/A2A entry points")
