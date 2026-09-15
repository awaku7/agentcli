from uagent.runtime.llm_error_classifier import LLMErrorClassifier


class _Error(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


def test_classifies_context_overflow_with_retry_request() -> None:
    result = LLMErrorClassifier().classify(_Error("context window exceeds maximum"))

    assert result.kind == "context_overflow"
    assert result.retry_request().reason == "context_overflow"


def test_classifies_stale_continuation_and_feature_fallback() -> None:
    classifier = LLMErrorClassifier()

    stale = classifier.classify(_Error("previous_response_id response not found"))
    feature = classifier.classify(
        _Error("model does not support tools", status_code=400)
    )

    assert stale.kind == "stale_continuation"
    assert feature.kind == "unsupported_feature"
    assert feature.retry_request().reason == "feature_fallback"


def test_classifies_structured_transport_metadata() -> None:
    result = LLMErrorClassifier().classify(_Error("busy", status_code=429))

    assert result.kind == "transport"
    assert result.status_code == 429
