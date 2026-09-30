from uagent.runtime.provider_cache import plan_provider_cache


def test_provider_cache_plan_maps_projection_changes_to_provider_actions():
    assert (
        plan_provider_cache(
            provider="vertexai",
            model="gemini-3-flash",
            projection_changed=True,
        ).action
        == "REBUILD"
    )
    assert (
        plan_provider_cache(
            provider="claude",
            model="claude-sonnet",
            projection_changed=True,
        ).action
        == "REANCHOR"
    )
    assert (
        plan_provider_cache(
            provider="openai",
            model="gpt-5",
            projection_changed=True,
            previous_response_id=True,
        ).action
        == "BYPASS"
    )


def test_provider_cache_plan_uses_responses_continuation_capability():
    assert (
        plan_provider_cache(
            provider="lmstudio",
            model="local-model",
            projection_changed=True,
            previous_response_id=True,
        ).action
        == "BYPASS"
    )
    assert (
        plan_provider_cache(
            provider="openrouter",
            model="some-model",
            projection_changed=True,
            previous_response_id=True,
        ).action
        == "NONE"
    )


def test_provider_cache_plan_reuses_unchanged_projection():
    plan = plan_provider_cache(
        provider="claude",
        model="claude-sonnet",
        projection_changed=False,
    )
    assert plan.action == "REUSE"
    assert plan.projection_changed is False
