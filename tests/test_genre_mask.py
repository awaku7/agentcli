import sys

from uagent.util_common import parse_startup_args


def _parse(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["uag"] + argv)
    args, _unknown = parse_startup_args()
    return args


def _genre_mask_help():
    from uagent.util_common import parse_startup_args as parse_fn
    import inspect

    src = inspect.getsource(parse_fn)
    for line in src.splitlines():
        if "Tool genre bitmask" in line:
            return line.strip()
    raise AssertionError("help text not found")


def _enabled_genres_after(mask):
    from uagent.tools import _genre_control_util as G

    G._ENABLED_GENRES.clear()
    from uagent.cli_startup import _apply_startup_tool_genre_mask

    _apply_startup_tool_genre_mask(mask)
    return set(G._ENABLED_GENRES)


def test_genre_mask_help_lists_all_genres():
    help_text = _genre_mask_help()
    from uagent.tools._genre_control_util import _GENRE_BITMAP

    total = sum(_GENRE_BITMAP.values())
    assert f"{total}=all" in help_text
    for genre, bit in _GENRE_BITMAP.items():
        assert f"{bit}={genre}" in help_text
    # stale values must be gone
    assert "1023=all" not in help_text
    assert "127=all" not in help_text


def test_genre_mask_parse_ok(monkeypatch):
    args = _parse(monkeypatch, ["--tool-genre-mask", "8191"])
    assert args["tool_genre_mask"] == 8191


def test_apply_full_mask_enables_all_genres():
    from uagent.tools._genre_control_util import _GENRE_BITMAP

    enabled = _enabled_genres_after(sum(_GENRE_BITMAP.values()))
    assert enabled == set(_GENRE_BITMAP)


def test_apply_single_bit_dev():
    assert _enabled_genres_after(1024) == {"dev"}


def test_apply_single_bit_basic():
    assert _enabled_genres_after(1) == {"basic"}


def test_apply_zero_is_noop():
    assert _enabled_genres_after(0) == set()
