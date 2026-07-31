"""Unit tests for src/uagent/realtime.py helper functions and configuration."""

from __future__ import annotations


from uagent import realtime


class TestRealtimeConfig:
    def test_provider_google_aliases(self, monkeypatch) -> None:
        monkeypatch.setenv("UAGENT_AUDIO_REALTIME_PROVIDER", "google")
        assert realtime._provider() == "google"

        monkeypatch.setenv("UAGENT_AUDIO_REALTIME_PROVIDER", "gemini")
        assert realtime._provider() == "gemini"

        monkeypatch.setenv("UAGENT_AUDIO_REALTIME_PROVIDER", "vertexai")
        assert realtime._provider() == "vertexai"

    def test_api_key_google(self, monkeypatch) -> None:
        monkeypatch.delenv("UAGENT_GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("UAGENT_GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("UAGENT_VERTEXAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("VERTEXAI_API_KEY", raising=False)

        monkeypatch.setenv("UAGENT_AUDIO_REALTIME_PROVIDER", "google")
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
        assert realtime._api_key() == "test-gemini-key"

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
        assert realtime._api_key() == "test-google-key"

    def test_depname_google(self, monkeypatch) -> None:
        monkeypatch.delenv("UAGENT_GOOGLE_REALTIME_DEPNAME", raising=False)
        monkeypatch.delenv("UAGENT_GEMINI_REALTIME_DEPNAME", raising=False)
        monkeypatch.delenv("UAGENT_VERTEXAI_REALTIME_DEPNAME", raising=False)

        assert realtime._depname("google") == "gemini-3.1-flash-live-preview"
        assert realtime._depname("gemini") == "gemini-3.1-flash-live-preview"
        assert realtime._depname("vertexai") == "gemini-3.1-flash-live-preview"

        monkeypatch.setenv("UAGENT_GEMINI_REALTIME_DEPNAME", "custom-gemini-model")
        assert realtime._depname("gemini") == "custom-gemini-model"

    def test_voice_google(self, monkeypatch) -> None:
        monkeypatch.delenv("UAGENT_GEMINI_REALTIME_VOICE", raising=False)
        monkeypatch.delenv("UAGENT_GOOGLE_REALTIME_VOICE", raising=False)
        assert realtime._voice("google") == "Puck"
        assert realtime._voice("gemini") == "Puck"

        monkeypatch.setenv("UAGENT_GEMINI_REALTIME_VOICE", "Kore")
        assert realtime._voice("gemini") == "Kore"

    def test_realtime_config_google(self) -> None:
        url, headers = realtime._realtime_config("gemini", "my-key")
        assert "generativelanguage.googleapis.com" in url
        assert "key=my-key" in url
        assert headers == {}

    def test_gemini_setup_message(self) -> None:
        msg = realtime._gemini_setup_message("gemini-3.1-flash-live-preview", voice="Puck")
        assert "setup" in msg
        assert msg["setup"]["model"] == "models/gemini-3.1-flash-live-preview"
        gen_config = msg["setup"]["generationConfig"]
        assert "AUDIO" in gen_config["responseModalities"]
        assert (
            gen_config["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"][
                "voiceName"
            ]
            == "Puck"
        )
        sys_inst = msg["setup"]["systemInstruction"]
        assert len(sys_inst["parts"]) == 1
        text = sys_inst["parts"][0]["text"]
        assert ("You are a helpful voice assistant." in text) or (
            "あなたは役に立つ音声アシスタントです。" in text
        )
