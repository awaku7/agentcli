"""Unit tests for audio_speech Grok/xAI TTS path (mocked HTTP)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uagent.tools import audio_speech_tool as ast


class TestGrokHelpers:
    def test_clamp_speed(self) -> None:
        assert ast._clamp_grok_speed(0.5) == pytest.approx(0.7)
        assert ast._clamp_grok_speed(2.0) == pytest.approx(1.5)
        assert ast._clamp_grok_speed(1.0) == pytest.approx(1.0)
        assert ast._clamp_grok_speed("bad") == pytest.approx(1.0)  # type: ignore[arg-type]

    def test_provider_xai_alias(self, monkeypatch) -> None:
        monkeypatch.setenv("UAGENT_AUDIO_SPEECH_PROVIDER", "xai")
        assert ast._provider() == "grok"

    def test_model_default_grok(self, monkeypatch) -> None:
        monkeypatch.delenv("UAGENT_GROK_SPEECH_DEPNAME", raising=False)
        monkeypatch.delenv("UAGENT_GROK_TTS_MODEL", raising=False)
        assert ast._model("grok") == "grok-tts"

    def test_mime_for_format(self) -> None:
        assert ast._mime_for_format("mp3") == "audio/mpeg"
        assert ast._mime_for_format("wav") == "audio/wav"


class TestGrokTtsBytes:
    def test_posts_expected_body(self, monkeypatch) -> None:
        monkeypatch.setenv("UAGENT_GROK_API_KEY", "test-key")
        monkeypatch.delenv("XAI_API_KEY", raising=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "audio/mpeg"}
        mock_resp.content = b"FAKE_MP3"
        mock_resp.text = ""

        with patch.object(ast.requests, "post", return_value=mock_resp) as post:
            out = ast._grok_tts_bytes(
                text="hello",
                voice_id="eve",
                language="en",
                speed=1.2,
                codec="mp3",
            )
        assert out == b"FAKE_MP3"
        assert post.call_count == 1
        args, kwargs = post.call_args
        assert args[0] == "https://api.x.ai/v1/tts"
        body = kwargs["json"]
        assert body["text"] == "hello"
        assert body["voice_id"] == "eve"
        assert body["language"] == "en"
        assert body["speed"] == pytest.approx(1.2)
        assert body["output_format"]["codec"] == "mp3"
        assert body["output_format"]["sample_rate"] == 24000
        assert body["output_format"]["bit_rate"] == 128000
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"
        assert kwargs["verify"] is True

    def test_json_base64_audio(self, monkeypatch) -> None:
        import base64

        monkeypatch.setenv("UAGENT_GROK_API_KEY", "k")
        raw = b"WAVDATA"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.json.return_value = {"audio": base64.b64encode(raw).decode("ascii")}
        mock_resp.text = ""

        with patch.object(ast.requests, "post", return_value=mock_resp):
            out = ast._grok_tts_bytes(
                text="hi",
                voice_id="ara",
                language="auto",
                speed=1.0,
                codec="wav",
            )
        assert out == raw

    def test_http_error(self, monkeypatch) -> None:
        monkeypatch.setenv("UAGENT_GROK_API_KEY", "k")
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.text = '{"error":"nope"}'
        mock_resp.content = b""

        with patch.object(ast.requests, "post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="xAI TTS HTTP 401"):
                ast._grok_tts_bytes(
                    text="hi",
                    voice_id="eve",
                    language="auto",
                    speed=1.0,
                    codec="mp3",
                )


class TestRunToolGrok:
    def test_success_writes_file(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("UAGENT_AUDIO_SPEECH_PROVIDER", "grok")
        monkeypatch.setenv("UAGENT_GROK_API_KEY", "k")
        monkeypatch.setenv("UAGENT_WORKDIR", str(tmp_path))
        # ensure_within_workdir uses workdir from context/env
        out = tmp_path / "out" / "speech.mp3"
        out.parent.mkdir(parents=True, exist_ok=True)

        with (
            patch.object(ast, "ensure_within_workdir", return_value=str(out)),
            patch.object(ast, "_grok_tts_bytes", return_value=b"AUDIO") as tts,
            patch.object(ast, "open_image_with_default_app"),
            patch.object(ast, "get_callbacks", return_value=None),
            patch.object(ast, "check_audio_output_support", return_value=None),
        ):
            result = ast.run_tool(
                {
                    "text": "hello world",
                    "output_path": str(out),
                    "voice": "eve",
                    "response_format": "mp3",
                }
            )
        data = json.loads(result)
        assert data.get("ok") is True or data.get("success") is True or "path" in str(
            data
        )
        assert out.read_bytes() == b"AUDIO"
        tts.assert_called_once()
        kwargs = tts.call_args.kwargs
        assert kwargs["text"] == "hello world"
        assert kwargs["voice_id"] == "eve"
        assert kwargs["codec"] == "mp3"

    def test_text_too_long(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("UAGENT_AUDIO_SPEECH_PROVIDER", "grok")
        monkeypatch.setenv("UAGENT_GROK_API_KEY", "k")
        out = tmp_path / "x.mp3"
        with (
            patch.object(ast, "ensure_within_workdir", return_value=str(out)),
            patch.object(ast, "check_audio_output_support", return_value=None),
        ):
            result = ast.run_tool(
                {
                    "text": "a" * (ast._GROK_TEXT_MAX + 1),
                    "output_path": str(out),
                }
            )
        assert "15000" in result or "too long" in result.lower() or "limit" in result.lower()
        assert not out.exists()

    def test_unsupported_format(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("UAGENT_AUDIO_SPEECH_PROVIDER", "grok")
        monkeypatch.setenv("UAGENT_GROK_API_KEY", "k")
        out = tmp_path / "x.opus"
        with (
            patch.object(ast, "ensure_within_workdir", return_value=str(out)),
            patch.object(ast, "check_audio_output_support", return_value=None),
        ):
            result = ast.run_tool(
                {
                    "text": "hi",
                    "output_path": str(out),
                    "response_format": "opus",
                }
            )
        low = result.lower()
        assert "opus" in low or "format" in low or "mp3" in low

    def test_gate_rejects(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("UAGENT_AUDIO_SPEECH_PROVIDER", "grok")
        out = tmp_path / "x.mp3"
        with (
            patch.object(ast, "ensure_within_workdir", return_value=str(out)),
            patch.object(
                ast,
                "check_audio_output_support",
                return_value="Model does not support audio output",
            ),
        ):
            result = ast.run_tool({"text": "hi", "output_path": str(out)})
        assert "audio" in result.lower()
        assert not out.exists()
