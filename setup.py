from __future__ import annotations

from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


class build_py(_build_py):
    """Copy top-level README.md into package as scheck/README.md during build.

    The repository source of truth is ./README.md.
    """

    def run(self):
        root = Path(__file__).resolve().parent
        src_readme = root / "README.md"
        dst_readme = root / "src" / "uagent" / "README.md"

        src_quickstart = root / "QUICKSTART.md"
        dst_quickstart = root / "src" / "uagent" / "QUICKSTART.md"

        if src_readme.exists():
            dst_readme.parent.mkdir(parents=True, exist_ok=True)
            dst_readme.write_text(
                src_readme.read_text(encoding="utf-8"), encoding="utf-8"
            )


        src_readme_ja = root / "README.ja.md"
        dst_readme_ja = root / "src" / "uagent" / "README.ja.md"

        src_quickstart_ja = root / "QUICKSTART.ja.md"
        dst_quickstart_ja = root / "src" / "uagent" / "QUICKSTART.ja.md"

        if src_readme_ja.exists():
            dst_readme_ja.parent.mkdir(parents=True, exist_ok=True)
            dst_readme_ja.write_text(src_readme_ja.read_text(encoding="utf-8"), encoding="utf-8")

        if src_quickstart_ja.exists():
            dst_quickstart_ja.parent.mkdir(parents=True, exist_ok=True)
            dst_quickstart_ja.write_text(src_quickstart_ja.read_text(encoding="utf-8"), encoding="utf-8")
        if src_quickstart.exists():
            dst_quickstart.parent.mkdir(parents=True, exist_ok=True)
            dst_quickstart.write_text(
                src_quickstart.read_text(encoding="utf-8"), encoding="utf-8"
            )

        super().run()


setup(cmdclass={"build_py": build_py})
