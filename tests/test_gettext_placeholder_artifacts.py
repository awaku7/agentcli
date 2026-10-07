from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "locales"


def test_gettext_catalogs_do_not_ship_placeholder_artifacts():
    offenders = []

    for path in sorted(LOCALES_DIR.glob("*/LC_MESSAGES/uag.po")):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "PH_" in line:
                offenders.append(
                    f"{path.relative_to(LOCALES_DIR)}:{line_number}: {line.strip()}"
                )

    for path in sorted(LOCALES_DIR.glob("*/LC_MESSAGES/uag.mo")):
        if b"PH_" in path.read_bytes():
            offenders.append(f"{path.relative_to(LOCALES_DIR)}: binary contains PH_")

    assert (
        not offenders
    ), "Placeholder artifacts remain in gettext catalogs:\n" + "\n".join(offenders)
