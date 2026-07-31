"""runtime_banner audio model resolution for :model / startup banner."""

from __future__ import annotations

from typing import Iterator

import pytest


@pytest.fixture()
def clean_audio_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    keys = [
        "UAGENT_PROVIDER",
        "UAGENT_AUDIO_SPEECH_PROVIDER",
        "UAGENT_AUDIO_TRANSCRIBE_PROVIDER",
        "UAGENT_OPENAI_API_KEY",
        "UAGENT_OPENAI_SPEECH_DEPNAME",
        "UAGENT_OPENAI_TRANSCRIBE_DEPNAME",
        "UAGENT_GROK_API_KEY",
        "XAI_API_KEY",
        "UAGENT_GROK_SPEECH_DEPNAME",
        "UAGENT_GROK_TTS_MODEL",
        "UAGENT_GROK_TRANSCRIBE_DEPNAME",
        "UAGENT_GROK_STT_MODEL",
        "UAGENT_GEMINI_API_KEY",
        "UAGENT_GEMINI_SPEECH_DEPNAME",
        "UAGENT_GEMINI_TRANSCRIBE_DEPNAME",
        "UAGENT_GEMINI_MODEL",
        "UAGENT_GOOGLE_CREDENTIALS",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "UAGENT_AZURE_SPEECH_DEPNAME",
        "UAGENT_AZURE_TRANSCRIBE_DEPNAME",
        "UAGENT_AZURE_BASE_URL",
        "UAGENT_AZURE_API_KEY",
        "UAGENT_AZURE_API_VERSION",
    ]
    for k in keys:
        monkeypatch.delenv(k, raising=False)
    yield


def test_audio_speech_openai_default(clean_audio_env, monkeypatch):
    from uagent.runtime.runtime_banner import _audio_model_info

    monkeypatch.setenv("UAGENT_PROVIDER", "openai")
    monkeypatch.setenv("UAGENT_OPENAI_API_KEY", "sk-test")
    assert _audio_model_info("speech") == ("openai", "gpt-4o-mini-tts")


def test_audio_transcribe_openai_default(clean_audio_env, monkeypatch):
    from uagent.runtime.runtime_banner import _audio_model_info

    monkeypatch.setenv("UAGENT_PROVIDER", "openai")
    monkeypatch.setenv("UAGENT_OPENAI_API_KEY", "sk-test")
    assert _audio_model_info("transcribe") == ("openai", "gpt-4o-mini-transcribe")


def test_audio_speech_grok_fallback_from_provider(clean_audio_env, monkeypatch):
    from uagent.runtime.runtime_banner import _audio_model_info

    monkeypatch.setenv("UAGENT_PROVIDER", "grok")
    monkeypatch.setenv("UAGENT_GROK_API_KEY", "xai-test")
    assert _audio_model_info("speech") == ("grok", "grok-tts")


def test_audio_transcribe_grok_fallback_from_provider(clean_audio_env, monkeypatch):
    from uagent.runtime.runtime_banner import _audio_model_info

    monkeypatch.setenv("UAGENT_PROVIDER", "grok")
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    assert _audio_model_info("transcribe") == ("grok", "grok-stt-batch")


def test_audio_speech_xai_alias(clean_audio_env, monkeypatch):
    from uagent.runtime.runtime_banner import _audio_model_info

    monkeypatch.setenv("UAGENT_AUDIO_SPEECH_PROVIDER", "xai")
    monkeypatch.setenv("UAGENT_GROK_API_KEY", "xai-test")
    monkeypatch.setenv("UAGENT_GROK_TTS_MODEL", "custom-tts")
    assert _audio_model_info("speech") == ("grok", "custom-tts")


def test_audio_speech_grok_missing_key(clean_audio_env, monkeypatch):
    from uagent.runtime.runtime_banner import _audio_model_info

    monkeypatch.setenv("UAGENT_PROVIDER", "grok")
    assert _audio_model_info("speech") is None


def test_cmd_model_shows_audio_fallback(clean_audio_env, monkeypatch, capsys):
    from types import SimpleNamespace
    from uagent.i18n import set_thread_lang
    from uagent.util_tools import _handle_cmd_model

    # :model UI uses gettext; pin English so assertions stay stable.
    set_thread_lang("en")
    monkeypatch.setenv("UAGENT_LANG", "en")
    monkeypatch.setenv("UAGENT_PROVIDER", "grok")
    monkeypatch.setenv("UAGENT_GROK_API_KEY", "xai-test")
    monkeypatch.setenv("UAGENT_GROK_DEPNAME", "grok-3")

    core = SimpleNamespace(tr=lambda s, **k: s)
    _handle_cmd_model("", core=core, tr=core.tr)
    out = capsys.readouterr().out
    assert "Audio Speech:" in out
    assert "grok-tts" in out
    assert "Audio Transcribe:" in out
    assert "grok-stt-batch" in out
    assert "fallback" in out.lower()
