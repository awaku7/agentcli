from types import SimpleNamespace

from uagent import llmcapa_util


def test_image_capability_helpers_read_structured_metadata(monkeypatch):
    image = SimpleNamespace(
        quality_values=("auto", "high", "xhigh", "max"),
        max_outputs=10,
    )
    monkeypatch.setattr(
        llmcapa_util,
        "get_capability",
        lambda model_id, provider: SimpleNamespace(image=image),
    )

    assert llmcapa_util.image_capability_values(
        "quality_values", "gpt-image-2.5-flare", "openai"
    ) == ("auto", "high", "xhigh", "max")
    assert llmcapa_util.image_capability_max_outputs(
        "gpt-image-2.5-flare", "openai"
    ) == 10
    assert (
        llmcapa_util.check_image_capability_value(
            "quality_values", "xhigh", "gpt-image-2.5-flare", "openai"
        )
        is None
    )
    assert llmcapa_util.check_image_capability_value(
        "quality_values", "hd", "gpt-image-2.5-flare", "openai"
    )


def test_image_capability_helpers_keep_unknown_models_permissive(monkeypatch):
    monkeypatch.setattr(
        llmcapa_util,
        "get_capability",
        lambda model_id, provider: SimpleNamespace(image=None),
    )

    assert llmcapa_util.image_capability_values(
        "quality_values", "custom-image", "openai"
    ) == ()
    assert llmcapa_util.image_capability_max_outputs(
        "custom-image", "openai"
    ) == 4
    assert (
        llmcapa_util.check_image_capability_value(
            "quality_values", "vendor-specific", "custom-image", "openai"
        )
        is None
    )


def test_image_tool_schemas_expose_extended_image_limits():
    from uagent.tools.generate_image_tool import TOOL_SPEC as generate_spec
    from uagent.tools.img2img_tool import TOOL_SPEC as edit_spec

    for spec in (generate_spec, edit_spec):
        properties = spec["function"]["parameters"]["properties"]
        assert properties["n"]["maximum"] == 10
        assert "xhigh" in properties["quality"]["enum"]
        assert "max" in properties["quality"]["enum"]
        assert properties["output_format"]["enum"] == ["png", "jpeg", "webp"]
        assert properties["output_compression"]["minimum"] == 0
        assert properties["output_compression"]["maximum"] == 100
