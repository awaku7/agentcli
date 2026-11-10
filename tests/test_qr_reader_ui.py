from __future__ import annotations

import json
from types import SimpleNamespace

from uagent.tools.qr_reader_ui import QRReaderWindow, _translate_ui


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


def test_ui_uses_translated_strings_and_formats_placeholders() -> None:
    text = _translate_ui(
        {
            "ui.camera_open_error": "Kamera %(index)s kann nicht geöffnet werden.",
        },
        "ui.camera_open_error",
        "Could not open camera %(index)s.",
        index=2,
    )

    assert text == "Kamera 2 kann nicht geöffnet werden."


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


def test_send_to_uag_emits_ascii_safe_json_for_unicode_payload(capsys) -> None:
    reader = object.__new__(QRReaderWindow)
    reader.last_data = "café 日本語"
    reader.root = SimpleNamespace(
        clipboard_clear=lambda: None,
        clipboard_append=lambda _text: None,
        update_idletasks=lambda: None,
    )
    reader.strings = {}
    reader.status = SimpleNamespace(set=lambda _text: None)
    reader.close = lambda: None

    reader.send_to_uag()

    output = capsys.readouterr().out.strip()
    assert output.isascii()
    assert json.loads(output) == {"text": "café 日本語"}


def test_open_image_stops_camera_before_processing_selected_image(monkeypatch) -> None:
    import uagent.tools.qr_reader_ui as qr_reader_ui

    actions: list[object] = []
    monkeypatch.setattr(
        qr_reader_ui.filedialog,
        "askopenfilename",
        lambda **_kwargs: "selected.png",
    )
    reader = object.__new__(QRReaderWindow)
    reader.root = SimpleNamespace(
        after_cancel=lambda callback_id: actions.append(("cancel", callback_id))
    )
    reader._camera_after_id = "after#9"
    reader.capture = SimpleNamespace(release=lambda: actions.append(("release", None)))
    reader.strings = {}
    reader.status = SimpleNamespace(set=lambda text: actions.append(("status", text)))
    reader.cv2 = SimpleNamespace(
        imread=lambda path: actions.append(("read", path)) or object()
    )
    reader._decode = lambda _frame: (["image QR"], None)
    reader._show_frame = lambda _frame: actions.append(("preview", None))
    reader._record_results = lambda values: actions.append(("record", values))

    reader.open_image()

    assert actions[:2] == [("cancel", "after#9"), ("release", None)]
    assert actions.index(("read", "selected.png")) > actions.index(("release", None))
    assert ("record", ["image QR"]) in actions


def test_duplicate_decode_updates_latest_payload_without_repeating_history(
    monkeypatch,
) -> None:
    import uagent.tools.qr_reader_ui as qr_reader_ui

    moments = iter([10.0, 10.5, 11.0])
    monkeypatch.setattr(qr_reader_ui.time, "monotonic", lambda: next(moments))
    inserted: list[str] = []
    reader = object.__new__(QRReaderWindow)
    reader._last_seen = {}
    reader.output = SimpleNamespace(
        insert=lambda _where, value: inserted.append(value),
        see=lambda _where: None,
    )
    reader.strings = {}
    reader.status = SimpleNamespace(set=lambda _text: None)
    reader.last_data = ""

    reader._record_results(["A"])
    reader._record_results(["B"])
    reader._record_results(["A"])

    assert reader.last_data == "A"
    assert len(inserted) == 2
    assert "A" in inserted[0]
    assert "B" in inserted[1]


def test_stop_camera_cancels_pending_frame_callback() -> None:
    cancelled: list[str] = []
    released: list[bool] = []
    reader = object.__new__(QRReaderWindow)
    reader._camera_after_id = "after#7"
    reader.strings = {}
    reader.root = SimpleNamespace(after_cancel=cancelled.append)
    reader.capture = SimpleNamespace(release=lambda: released.append(True))
    reader.status = SimpleNamespace(set=lambda _text: None)

    reader.stop_camera()

    assert cancelled == ["after#7"]
    assert released == [True]
    assert reader._camera_after_id is None
    assert reader.capture is None
