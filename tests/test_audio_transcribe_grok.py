"""Unit tests for audio_transcribe Grok/xAI STT path (mocked HTTP)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uagent.tools import audio_transcribe_tool as att


class TestGrokHelpers:
    def test_provider_xai_alias(self, monkeypatch) -> None:
        monkeypatch.setenv("UAGENT_AUDIO_TRANSCRIBE_PROVIDER", "xai")
        assert att._provider() == "grok"

    def test_model_default_grok(self, monkeypatch) -> None:
        monkeypatch.delenv("UAGENT_GROK_TRANSCRIBE_DEPNAME", raising=False)
        monkeypatch.delenv("UAGENT_GROK_STT_MODEL", raising=False)
        assert att._model("grok") == "grok-stt-batch"

    def test_normalize_keyterms_truncates(self) -> None:
        long = "x" * 80
        out = att._normalize_keyterms([long, "ok", "", "y" * 10])
        assert out[0] == "x" * att._GROK_KEYTERM_LEN
        assert "ok" in out
        assert len(out) <= att._GROK_KEYTERM_MAX

    def test_normalize_keyterms_string(self) -> None:
        assert att._normalize_keyterms("hello") == ["hello"]


class TestGrokSttHttp:
    def test_posts_multipart_file(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("UAGENT_GROK_API_KEY", "test-key")
        monkeypatch.delenv("XAI_API_KEY", raising=False)
        audio = tmp_path / "sample.wav"
        audio.write_bytes(b"RIFF....WAVEfmt ")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "text": "hello world",
            "language": "en",
            "duration": 1.5,
            "words": [{"text": "hello", "start": 0.0, "end": 0.5}],
        }
        mock_resp.text = ""

        with patch.object(att.requests, "post", return_value=mock_resp) as post:
            out = att._grok_stt(
                path=str(audio),
                url=None,
                language="en",
                diarize=True,
                keyterms=["uagent", "xai"],
                filler_words=True,
                itn_format=True,
            )
        assert out["text"] == "hello world"
        assert post.call_count == 1
        args, kwargs = post.call_args
        assert args[0] == "https://api.x.ai/v1/stt"
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"
        assert kwargs["verify"] is True
        data_fields = kwargs["data"]
        # list of tuples
        as_dict_multi = {}
        for k, v in data_fields:
            as_dict_multi.setdefault(k, []).append(v)
        assert as_dict_multi.get("language") == ["en"]
        assert as_dict_multi.get("diarize") == ["true"]
        assert as_dict_multi.get("filler_words") == ["true"]
        assert as_dict_multi.get("format") == ["true"]
        assert as_dict_multi.get("keyterm") == ["uagent", "xai"]
        assert "file" in kwargs["files"]

    def test_posts_url_only(self, monkeypatch) -> None:
        monkeypatch.setenv("UAGENT_GROK_API_KEY", "k")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "from url", "language": "ja"}
        mock_resp.text = ""

        with patch.object(att.requests, "post", return_value=mock_resp) as post:
            out = att._grok_stt(
                path=None,
                url="https://example.com/a.mp3",
                language="ja",
                diarize=False,
                keyterms=[],
                filler_words=False,
                itn_format=False,
            )
        assert out["text"] == "from url"
        data_fields = dict(post.call_args.kwargs["data"])
        assert data_fields["url"] == "https://example.com/a.mp3"
        assert post.call_args.kwargs.get("files") is None

    def test_http_error(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("UAGENT_GROK_API_KEY", "k")
        audio = tmp_path / "a.mp3"
        audio.write_bytes(b"ID3")
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = '{"error":"nope"}'
        mock_resp.json.side_effect = ValueError("no json")

        with patch.object(att.requests, "post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="xAI STT HTTP 401"):
                att._grok_stt(
                    path=str(audio),
                    url=None,
                    language="en",
                    diarize=False,
                    keyterms=[],
                    filler_words=False,
                    itn_format=False,
                )

    def test_file_too_large(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("UAGENT_GROK_API_KEY", "k")
        audio = tmp_path / "big.wav"
        audio.write_bytes(b"x")
        # fake huge size via Path.stat patch inside _grok_stt uses Path(path).stat()
        real_stat = Path.stat

        class FakeStat:
            st_size = att._GROK_FILE_MAX_BYTES + 1

        def fake_stat(self, *a, **k):
            if self == audio or str(self) == str(audio):
                return FakeStat()
            return real_stat(self, *a, **k)

        with patch.object(Path, "stat", fake_stat):
            with pytest.raises(RuntimeError, match="500"):
                att._grok_stt(
                    path=str(audio),
                    url=None,
                    language="en",
                    diarize=False,
                    keyterms=[],
                    filler_words=False,
                    itn_format=False,
                )


class TestRunToolGrok:
    def test_success_file(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("UAGENT_AUDIO_TRANSCRIBE_PROVIDER", "grok")
        monkeypatch.setenv("UAGENT_GROK_API_KEY", "k")
        monkeypatch.setenv("UAGENT_WORKDIR", str(tmp_path))
        audio = tmp_path / "clip.wav"
        audio.write_bytes(b"RIFF")

        payload = {
            "text": "transcribed text",
            "language": "en",
            "duration": 2.0,
            "words": [{"text": "transcribed", "start": 0.0, "end": 1.0}],
        }
        with (
            patch.object(att, "ensure_within_workdir", return_value=str(audio)),
            patch.object(att, "_grok_stt", return_value=payload) as stt,
            patch.object(att, "check_audio_input_support", return_value=None),
        ):
            result = att.run_tool(
                {
                    "path": str(audio),
                    "language": "en",
                    "diarize": True,
                    "keyterm": ["foo"],
                    "fmt": "json",
                }
            )
        data = json.loads(result)
        assert data.get("ok") is True or data.get("success") is True
        body = data.get("data") or data
        assert body.get("text") == "transcribed text"
        assert body.get("provider") == "grok"
        assert body.get("model") == "grok-stt-batch"
        assert body.get("words") is not None
        stt.assert_called_once()
        kwargs = stt.call_args.kwargs
        assert kwargs["diarize"] is True
        assert kwargs["keyterms"] == ["foo"]

    def test_success_url(self, monkeypatch) -> None:
        monkeypatch.setenv("UAGENT_AUDIO_TRANSCRIBE_PROVIDER", "grok")
        monkeypatch.setenv("UAGENT_GROK_API_KEY", "k")
        with (
            patch.object(
                att,
                "_grok_stt",
                return_value={"text": "remote", "language": "ja"},
            ) as stt,
            patch.object(att, "check_audio_input_support", return_value=None),
        ):
            result = att.run_tool({"url": "https://example.com/a.wav"})
        data = json.loads(result)
        body = data.get("data") or data
        assert body.get("text") == "remote"
        stt.assert_called_once()
        assert stt.call_args.kwargs["url"] == "https://example.com/a.wav"
        assert stt.call_args.kwargs["path"] is None

    def test_missing_path_and_url(self, monkeypatch) -> None:
        monkeypatch.setenv("UAGENT_AUDIO_TRANSCRIBE_PROVIDER", "grok")
        with patch.object(att, "check_audio_input_support", return_value=None):
            result = att.run_tool({})
        low = result.lower()
        assert "path" in low or "url" in low
        data = json.loads(result)
        assert data.get("ok") is False or data.get("success") is False

    def test_gate_rejects(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("UAGENT_AUDIO_TRANSCRIBE_PROVIDER", "grok")
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"x")
        with (
            patch.object(att, "ensure_within_workdir", return_value=str(audio)),
            patch.object(
                att,
                "check_audio_input_support",
                return_value="Model does not support audio input",
            ),
        ):
            result = att.run_tool({"path": str(audio)})
        assert "audio" in result.lower()
        data = json.loads(result)
        assert data.get("ok") is False or data.get("success") is False
