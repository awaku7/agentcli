from __future__ import annotations


def test_request_roundtrip_is_json_and_atomic(tmp_path) -> None:
    from uagent.tools import windows_uac_launcher

    request_path, result_path = windows_uac_launcher.create_request_paths(str(tmp_path))
    windows_uac_launcher.write_request(request_path, {"action": "tcp_syn", "port": 443})
    result_path.write_text('{"ok":true}', encoding="utf-8")

    assert windows_uac_launcher.read_result(result_path) == {"ok": True}
    assert request_path.exists()
    assert not request_path.with_suffix(".json.tmp").exists()


def test_wait_for_result_reads_existing_file(tmp_path) -> None:
    from uagent.tools import windows_uac_launcher

    result_path = tmp_path / "result.json"
    result_path.write_text(
        '{"ok":false,"code":"ELEVATION_CANCELLED"}', encoding="utf-8"
    )

    result = windows_uac_launcher.wait_for_result(result_path, timeout=0.1)

    assert result["code"] == "ELEVATION_CANCELLED"
