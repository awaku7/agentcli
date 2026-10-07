import json
from pathlib import Path


CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "uagent"
    / "tools"
    / "coverage_report_tool.json"
)


def test_coverage_report_fil_and_nynorsk_search_terms_are_localized() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    assert catalog["fil"]["x_search_terms"] == [
        "saklaw",
        "saklaw ng pagsubok",
        "saklaw ng linya",
        "saklaw ng sangay",
        "lcov",
    ]
    assert catalog["nn"]["x_search_terms"] == [
        "dekning",
        "testdekning",
        "linjedekning",
        "greindekning",
        "lcov",
    ]
