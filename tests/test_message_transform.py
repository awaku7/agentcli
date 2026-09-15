from uagent.runtime.message_transform import MessageTransformPipeline


def test_pipeline_does_not_mutate_history_and_normalizes_surrogates() -> None:
    messages = [{"role": "user", "content": "x" + chr(0xD800)}]

    result = MessageTransformPipeline().apply(messages)

    assert messages[0]["content"] == "x" + chr(0xD800)
    assert result.messages[0]["content"] == "x�"
    assert result.applied == ("surrogate_normalization",)


def test_translation_happens_before_provider_projection_boundary() -> None:
    seen: list[str] = []
    result = MessageTransformPipeline().apply(
        [{"role": "user", "content": "hello"}, {"role": "tool", "content": "keep"}],
        translator=lambda text: seen.append(text) or "translated",
    )

    assert seen == ["hello"]
    assert [message["content"] for message in result.messages] == ["translated", "keep"]
    assert result.applied == ("surrogate_normalization", "translation")
