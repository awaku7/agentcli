from uagent.runtime.provider_round_dispatcher import dispatch_provider_round


def test_dispatcher_prefers_registry_result() -> None:
    calls: list[str] = []

    def registry(**kwargs):
        calls.append("registry")
        assert kwargs == {"value": 1}
        return (True, "registry")

    def legacy(**kwargs):
        calls.append("legacy")
        return (True, "legacy")

    def openai(**kwargs):
        calls.append("openai")
        return (True, "openai")

    result = dispatch_provider_round(
        registry_runner=registry,
        legacy_runner=legacy,
        openai_runner=openai,
        registry_kwargs={"value": 1},
        legacy_kwargs={},
        openai_kwargs={},
    )

    assert result.source == "registry"
    assert result.result == (True, "registry")
    assert calls == ["registry"]


def test_dispatcher_falls_back_in_order_and_preserves_falsy_results() -> None:
    calls: list[str] = []

    def registry(**kwargs):
        calls.append("registry")
        return None

    def legacy(**kwargs):
        calls.append("legacy")
        return None

    def openai(**kwargs):
        calls.append("openai")
        return ()

    result = dispatch_provider_round(
        registry_runner=registry,
        legacy_runner=legacy,
        openai_runner=openai,
        registry_kwargs={},
        legacy_kwargs={},
        openai_kwargs={},
    )

    assert result.source == "openai_compatible"
    assert result.result == ()
    assert calls == ["registry", "legacy", "openai"]


def test_dispatcher_can_disable_registry_for_judgment_mode() -> None:
    calls: list[str] = []

    def legacy(**kwargs):
        calls.append("legacy")
        return "legacy-result"

    def openai(**kwargs):
        calls.append("openai")
        return "openai-result"

    result = dispatch_provider_round(
        registry_runner=None,
        legacy_runner=legacy,
        openai_runner=openai,
        registry_kwargs={},
        legacy_kwargs={},
        openai_kwargs={},
    )

    assert result.source == "legacy"
    assert result.result == "legacy-result"
    assert calls == ["legacy"]


def test_dispatcher_treats_any_non_none_registry_result_as_owned() -> None:
    """A falsy provider result must not accidentally trigger a fallback."""

    for registry_result in (False, "", ()):
        calls: list[str] = []

        def registry(**kwargs):
            calls.append("registry")
            return registry_result

        def legacy(**kwargs):
            calls.append("legacy")
            return "legacy-result"

        def openai(**kwargs):
            calls.append("openai")
            return "openai-result"

        result = dispatch_provider_round(
            registry_runner=registry,
            legacy_runner=legacy,
            openai_runner=openai,
            registry_kwargs={},
            legacy_kwargs={},
            openai_kwargs={},
        )

        assert result.source == "registry"
        assert result.result == registry_result
        assert calls == ["registry"]
