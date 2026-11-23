from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from uagent.decision import (
    DecisionKind,
    DecisionQuestion,
    DecisionRequest,
    DecisionSettings,
    create_decision_provider,
)
from uagent.decision.google import (
    GoogleDecisionConfig,
    GoogleDecisionConfigurationError,
    GoogleDecisionError,
    GoogleDecisionProvider,
    _decisions_url,
)


@pytest.fixture(autouse=True)
def _unknown_llmcapa_decision(monkeypatch):
    """Keep tests independent of the installed llmcapa model catalog."""
    monkeypatch.setattr(
        "uagent.decision.capabilities.get_capability", lambda *_a, **_k: None
    )


class FakeResponse:
    def __init__(self, payload, *, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeClient:
    def __init__(self, response=None, *, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.closed = False

    def post(self, url, *, headers, json):
        self.calls.append({"url": url, "headers": dict(headers), "json": json})
        if self.error is not None:
            raise self.error
        return self.response

    def close(self):
        self.closed = True


def _settings():
    return DecisionSettings(provider="google", source="env")


def _environ(**overrides):
    values = {
        "UAGENT_DECISION_GOOGLE_API_KEY": "secret-key",
        "UAGENT_DECISION_GOOGLE_DEPNAME": "gemini-decision-1",
        "UAGENT_DECISION_GOOGLE_BASE_URL": (
            "https://generativelanguage.googleapis.com/v1beta"
        ),
    }
    values.update(overrides)
    return values


def _response(answers):
    return FakeResponse({"model": "gemini-decision-1", "answers": answers})


def _bool_answer(noul=0.9, confidence=0.9):
    return {"type": "noul", "noul": noul, "confidence": confidence}


def test_google_config_defaults_and_hides_api_key():
    config = GoogleDecisionConfig.from_environment(
        {"UAGENT_DECISION_GOOGLE_API_KEY": "top-secret"}
    )

    assert config.model == "gemini-decision-1"
    assert config.base_url == "https://generativelanguage.googleapis.com/v1beta"
    assert config.api_key == "top-secret"
    assert "top-secret" not in repr(config)


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({"UAGENT_DECISION_GOOGLE_API_KEY": "decision-key"}, "decision-key"),
        ({"UAGENT_GEMINI_API_KEY": "gemini-key"}, "gemini-key"),
        ({"UAGENT_GOOGLE_API_KEY": "uag-google-key"}, "uag-google-key"),
        ({"GOOGLE_API_KEY": "google-key"}, "google-key"),
    ],
)
def test_google_api_key_sources(environ, expected):
    assert GoogleDecisionConfig.from_environment(environ).api_key == expected


def test_google_requires_api_key_when_adapter_is_created():
    with pytest.raises(GoogleDecisionConfigurationError, match="GOOGLE_API_KEY"):
        GoogleDecisionProvider(settings=_settings(), environ={}, client=FakeClient())


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        (
            "https://generativelanguage.googleapis.com/v1beta",
            "https://generativelanguage.googleapis.com/v1beta/decisions",
        ),
        (
            "https://generativelanguage.googleapis.com/v1beta/decisions",
            "https://generativelanguage.googleapis.com/v1beta/decisions",
        ),
        (
            "https://example.test/custom/decisions",
            "https://example.test/custom/decisions",
        ),
        (
            "https://example.test",
            "https://example.test/v1beta/decisions",
        ),
    ],
)
def test_decisions_url(base_url, expected):
    assert _decisions_url(base_url) == expected


def test_registry_creates_google_adapter():
    provider = create_decision_provider(
        _settings(), environ=_environ(), client=FakeClient()
    )

    assert isinstance(provider, GoogleDecisionProvider)
    assert provider.name == "google"
    assert provider.model == "gemini-decision-1"


def test_google_decisions_api_translates_all_question_kinds():
    client = FakeClient(
        _response(
            {
                "ready": _bool_answer(0.9, 0.88),
                "route": {
                    "type": "choice",
                    "choice": "CONTINUE",
                    "probabilities": {"COMPLETE": 0.1, "CONTINUE": 0.9},
                    "confidence": 0.9,
                },
                "risk": {
                    "type": "score",
                    "score": 1.5,
                    "probabilities": {"0": 0.1, "1": 0.7, "2": 0.2},
                    "legend": {"0": "low", "1": "medium", "2": "high"},
                    "confidence": 0.7,
                },
            }
        )
    )
    provider = GoogleDecisionProvider(
        settings=_settings(), environ=_environ(), client=client
    )
    request = DecisionRequest(
        state={"goal": "finish", "status": "in progress"},
        questions=(
            DecisionQuestion(
                "ready",
                DecisionKind.BOOLEAN,
                "Is this ready?",
                metadata={"criteria": {"true": "ready", "false": "not ready"}},
            ),
            DecisionQuestion(
                "route",
                DecisionKind.CHOICE,
                "Stop or continue?",
                choices=("COMPLETE", "CONTINUE"),
                metadata={
                    "criteria": {"COMPLETE": "finished", "CONTINUE": "more work"}
                },
            ),
            DecisionQuestion(
                "risk",
                DecisionKind.SCORE,
                "Rate risk.",
                choices=("low", "medium", "high"),
                metadata={"criteria": ["low risk", "medium risk", "high risk"]},
            ),
        ),
        metadata={"source": "ticket"},
    )

    result = provider.decide(request)

    call = client.calls[0]
    assert call["url"] == "https://generativelanguage.googleapis.com/v1beta/decisions"
    assert call["headers"]["x-goog-api-key"] == "secret-key"
    assert call["json"] == {
        "model": "gemini-decision-1",
        "input": '{"state":{"goal":"finish","status":"in progress"},"metadata":{"source":"ticket"}}',
        "questions": {
            "ready": {
                "type": "noul",
                "instructions": "Is this ready?",
                "criteria": {
                    "true_description": "ready",
                    "false_description": "not ready",
                },
            },
            "route": {
                "type": "choice",
                "instructions": "Stop or continue?",
                "criteria": {"COMPLETE": "finished", "CONTINUE": "more work"},
            },
            "risk": {
                "type": "score",
                "instructions": "Rate risk.",
                "criteria": ["low risk", "medium risk", "high risk"],
            },
        },
    }
    assert result.provider == "google"
    assert result.model == "gemini-decision-1"
    assert result.answers["ready"].value is True
    assert result.answers["ready"].confidence == pytest.approx(0.88)
    assert result.answers["ready"].calibrated is True
    assert result.answers["ready"].metadata["probability_true"] == pytest.approx(0.9)
    assert result.answers["route"].value == "CONTINUE"
    assert result.answers["route"].metadata["probabilities"][
        "CONTINUE"
    ] == pytest.approx(0.9)
    assert result.answers["risk"].value == pytest.approx(1.5)
    assert result.answers["risk"].metadata["legend"]["1"] == "medium"


def test_google_rejects_model_llmcapa_marks_without_decision_support(monkeypatch):
    seen = []
    decision = SimpleNamespace(decision=False)
    monkeypatch.setattr(
        "uagent.decision.capabilities.get_capability",
        lambda model, provider, *, scoped_only: (
            seen.append((model, provider, scoped_only))
            or SimpleNamespace(decision=decision)
        ),
    )
    client = FakeClient(_response({"flag": _bool_answer()}))
    provider = GoogleDecisionProvider(
        settings=_settings(), environ=_environ(), client=client
    )

    with pytest.raises(
        GoogleDecisionError, match="not documented as supporting typed Decision API"
    ):
        provider.decide(
            DecisionRequest("context", (DecisionQuestion("flag", "boolean", "?"),))
        )

    assert seen == [("gemini-decision-1", "google", True)]
    assert client.calls == []


def test_google_accepts_llmcapa_decision_capabilities(monkeypatch):
    decision = SimpleNamespace(
        decision=True,
        question_kinds=("noul", "choice", "score"),
        answer_fields=(
            "noul",
            "confidence",
            "choice",
            "probabilities",
            "score",
            "legend",
        ),
    )
    monkeypatch.setattr(
        "uagent.decision.capabilities.get_capability",
        lambda *_args, **_kwargs: SimpleNamespace(decision=decision),
    )
    client = FakeClient(_response({"flag": _bool_answer()}))
    provider = GoogleDecisionProvider(
        settings=_settings(), environ=_environ(), client=client
    )

    result = provider.decide(
        DecisionRequest("context", (DecisionQuestion("flag", "boolean", "?"),))
    )

    assert result.answers["flag"].value is True
    assert len(client.calls) == 1


def test_google_rejects_invalid_answers_and_duplicate_question_ids():
    question = DecisionQuestion("flag", "boolean", "Is it true?")
    provider = GoogleDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(_response({"flag": _bool_answer(1.0, 0.9)})),
    )
    with pytest.raises(GoogleDecisionError, match="outside \\[0.01, 0.99\\]"):
        provider.decide(DecisionRequest("context", (question,)))

    with pytest.raises(GoogleDecisionError, match="duplicate question ids"):
        provider.decide(DecisionRequest("context", (question, question)))


def test_google_rejects_more_than_1000_questions_before_request():
    questions = tuple(
        DecisionQuestion(f"q{index}", "boolean", "Is it true?") for index in range(1001)
    )
    client = FakeClient(_response({}))
    provider = GoogleDecisionProvider(
        settings=_settings(), environ=_environ(), client=client
    )

    with pytest.raises(GoogleDecisionError, match="at most 1000 questions"):
        provider.decide(DecisionRequest("context", questions))

    assert client.calls == []


def test_google_rejects_missing_unexpected_and_duplicate_answers():
    question = DecisionQuestion("flag", "boolean", "Is it true?")
    provider = GoogleDecisionProvider(
        settings=_settings(), environ=_environ(), client=FakeClient(_response({}))
    )
    with pytest.raises(GoogleDecisionError, match="missing answer 'flag'"):
        provider.decide(DecisionRequest("context", (question,)))

    provider = GoogleDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(_response({"flag": _bool_answer(), "extra": _bool_answer()})),
    )
    with pytest.raises(GoogleDecisionError, match="unexpected answer"):
        provider.decide(DecisionRequest("context", (question,)))


def test_google_requires_complete_probability_and_rubric_details():
    choice = DecisionQuestion("route", "choice", "Choose a route", choices=("A", "B"))
    provider = GoogleDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(
            _response(
                {
                    "route": {
                        "type": "choice",
                        "choice": "A",
                        "probabilities": {"A": 0.8},
                        "confidence": 0.8,
                    }
                }
            )
        ),
    )
    with pytest.raises(
        GoogleDecisionError, match="does not match the requested options"
    ):
        provider.decide(DecisionRequest("context", (choice,)))


def test_google_redacts_api_key_and_keeps_injected_client_caller_owned():
    class ErrorResponse(FakeResponse):
        text = "request failed using secret-key"

    client = FakeClient(ErrorResponse({}, status_code=401))
    provider = GoogleDecisionProvider(
        settings=_settings(), environ=_environ(), client=client
    )
    with pytest.raises(GoogleDecisionError) as exc_info:
        provider.decide(
            DecisionRequest("context", (DecisionQuestion("flag", "boolean", "?"),))
        )
    assert "secret-key" not in str(exc_info.value)
    provider.close()
    assert not client.closed


def test_google_http_errors_are_wrapped():
    provider = GoogleDecisionProvider(
        settings=_settings(),
        environ=_environ(),
        client=FakeClient(error=httpx.ConnectError("network failure")),
    )
    with pytest.raises(GoogleDecisionError, match="ConnectError"):
        provider.decide(
            DecisionRequest("context", (DecisionQuestion("flag", "boolean", "?"),))
        )
