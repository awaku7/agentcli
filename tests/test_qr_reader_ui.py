from __future__ import annotations

from uagent.tools.qr_reader_ui import QRReaderWindow


class MultiCodeDetector:
    def detectAndDecodeMulti(self, _frame):
        return True, ("https://example.com", "hello"), "corners"

    def detectAndDecode(self, _frame):
        raise AssertionError("single-code fallback should not run")


class SingleCodeDetector:
    def detectAndDecodeMulti(self, _frame):
        return False, (), None, ()

    def detectAndDecode(self, _frame):
        return "single result", "corners", None


def test_decoder_returns_all_nonempty_multi_results() -> None:
    reader = object.__new__(QRReaderWindow)
    reader.detector = MultiCodeDetector()

    values, points = reader._decode(object())

    assert values == ["https://example.com", "hello"]
    assert points == "corners"


def test_decoder_falls_back_to_single_qr_api() -> None:
    reader = object.__new__(QRReaderWindow)
    reader.detector = SingleCodeDetector()

    values, points = reader._decode(object())

    assert values == ["single result"]
    assert points == "corners"
