from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "uagent" / "tools"


def test_localized_search_terms_have_english_fallback() -> None:
    missing = []
    for path in sorted(TOOLS_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if '"x_search_terms": _(' in text and '"x_search_terms_en"' not in text:
            missing.append(path.name)

    assert not missing, (
        "Tools with localized x_search_terms must also define "
        'function["x_search_terms_en"]: ' + ", ".join(missing)
    )
