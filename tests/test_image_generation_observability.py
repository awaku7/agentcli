from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from uagent.tools.generate_image_tool import _run_openai_images as real_images_api
from uagent.runtime.logging_setup import log_event
from uagent.runtime.observability import runtime
from uagent.runtime.observability.image_generation import record_image_usage
from uagent.runtime.observability.otel_backend import OpenTelemetryBackend
from uagent.runtime.observability.settings import ObservabilitySettings


@pytest.fixture
def image_tool(monkeypatch, tmp_path):
    from uagent.tools import generate_image_tool as tool
    from uagent import llmcapa_util
    from uagent.tools.context import ToolCallbacks

    monkeypatch.setattr(tool, "get_callbacks", lambda: ToolCallbacks(is_gui=True))
    monkeypatch.setattr(tool, "_get_provider", lambda: "openai")
    monkeypatch.setattr(tool, "_get_image_depname", lambda *args: "gpt-image-1")
    monkeypatch.setenv("UAGENT_IMAGE_OPEN", "0")
    monkeypatch.setenv("UAGENT_IMG_GENERATE_DEBUG", "0")
    for name in (
        "check_image_output_support",
        "check_image_size",
        "check_image_streaming",
        "check_image_quality",
        "check_image_output_format",
        "check_image_background",
    ):
        if hasattr(llmcapa_util, name):
            monkeypatch.setattr(llmcapa_util, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(
        llmcapa_util, "supports_responses_image_tool", lambda *args: False
    )
    monkeypatch.setattr(
        "uagent.runtime.artifact_helpers.register_artifacts",
        lambda *args, **kwargs: [
            {
                "artifact_id": "a" * 32,
                "stored_path": "SECRET_PATH",
                "metadata": {"api_key": "NEVER_EXPORT"},
            }
        ],
    )

    def provider(**kwargs):
        record_image_usage({"input_tokens": 11, "output_tokens": 23})
        record_image_usage({"input_tokens": 2, "output_tokens": 3})
        return {"b64_list": ["aW1hZ2UtYnl0ZXM="], "url_list": [], "items": []}

    monkeypatch.setattr(tool, "_run_openai_images", provider)
    return tool, {
        "prompt": "a blue bird",
        "output_dir": str(tmp_path),
        "include_base64": True,
    }


def _run(monkeypatch, tool, args, *, capture=True):
    from uagent import tools

    settings = ObservabilitySettings(
        enabled=True,
        capture_content=capture,
        capture_categories=frozenset({"tool_arguments", "tool_result"}),
    )
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    backend = OpenTelemetryBackend(
        tracer=provider.get_tracer(__name__), provider=provider, settings=settings
    )
    monkeypatch.setattr(runtime, "get_observability_backend", lambda: backend)
    monkeypatch.setattr(
        "uagent.runtime.observability.image_generation.get_observability_settings",
        lambda: settings,
    )
    runtime._reset_runtime_observability_for_tests()
    try:
        log_event("tool.dispatch", tool="generate_image", tool_call_id="call-image-1")
        result = tools._call_tool_runner(
            "generate_image", tool.run_tool, args, tool_call_id="call-image-1"
        )
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        return result, spans[0]
    finally:
        runtime._reset_runtime_observability_for_tests()
        backend.shutdown()


def test_builtin_image_runner_exports_metadata_usage_and_reviewed_content(
    monkeypatch, image_tool
):
    tool, args = image_tool
    result, span = _run(monkeypatch, tool, args)
    assert json.loads(result)["ok"] is True
    attrs = dict(span.attributes)
    assert attrs["gen_ai.tool.name"] == "generate_image"
    assert attrs["gen_ai.tool.call.id"] == "call-image-1"
    assert attrs["gen_ai.request.model"] == "gpt-image-1"
    assert attrs["uag.image.generated_count"] == 1
    assert attrs["gen_ai.usage.input_tokens"] == 13
    assert attrs["gen_ai.usage.output_tokens"] == 26
    assert json.loads(attrs["gen_ai.tool.call.arguments"]) == {"prompt": "a blue bird"}
    summary = json.loads(attrs["gen_ai.tool.call.result"])
    assert summary == {"ok": True, "generated_count": 1, "artifact_ids": ["a" * 32]}
    assert span.status.status_code.name == "OK"
    assert all(
        secret not in str(attrs)
        for secret in (
            args["output_dir"],
            "SECRET_PATH",
            "NEVER_EXPORT",
            "aW1hZ2UtYnl0ZXM=",
            "data_base64",
        )
    )


def test_image_metadata_survives_with_content_capture_off(monkeypatch, image_tool):
    tool, args = image_tool
    _, span = _run(monkeypatch, tool, args, capture=False)
    assert span.attributes["gen_ai.tool.name"] == "generate_image"
    assert span.attributes["uag.image.generated_count"] == 1
    assert "gen_ai.tool.call.arguments" not in span.attributes
    assert "gen_ai.tool.call.result" not in span.attributes
    assert "a blue bird" not in str(dict(span.attributes))


def test_image_returned_error_is_an_error_span_without_raw_exception(
    monkeypatch, image_tool
):
    tool, args = image_tool

    def fail(**kwargs):
        raise RuntimeError("NEVER_EXPORT_PROVIDER_SECRET")

    monkeypatch.setattr(tool, "_run_openai_images", fail)
    result, span = _run(monkeypatch, tool, args)
    assert "NEVER_EXPORT_PROVIDER_SECRET" in result
    assert span.status.status_code.name == "ERROR"
    assert json.loads(span.attributes["gen_ai.tool.call.result"]) == {"ok": False}
    assert "NEVER_EXPORT_PROVIDER_SECRET" not in str(dict(span.attributes))
    assert "gen_ai.usage.input_tokens" not in span.attributes


def test_missing_and_invalid_usage_are_not_fabricated(monkeypatch, image_tool):
    tool, args = image_tool

    def provider(**kwargs):
        record_image_usage({"input_tokens": True, "output_tokens": -1})
        return {"b64_list": ["aW1hZ2UtYnl0ZXM="], "url_list": [], "items": []}

    monkeypatch.setattr(tool, "_run_openai_images", provider)
    _, span = _run(monkeypatch, tool, args)
    assert "gen_ai.usage.input_tokens" not in span.attributes
    assert "gen_ai.usage.output_tokens" not in span.attributes


@pytest.mark.parametrize("stream", [False, True])
def test_real_images_api_extracts_usage_and_streaming_does_not_double_count(
    monkeypatch, image_tool, stream
):
    import openai
    from uagent.providers import util_providers

    tool, args = image_tool
    monkeypatch.setattr(tool, "_run_openai_images", real_images_api)
    monkeypatch.setattr(
        tool,
        "_img_env",
        lambda *args, **kwargs: (
            "https://api.example.test/v1" if args[2] == "base_url" else "test-key"
        ),
    )
    monkeypatch.setattr(util_providers, "make_httpx_client", lambda **kwargs: object())
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        if stream:
            return iter(
                [
                    {
                        "type": "image_generation.partial_image",
                        "b64_json": "aW1hZ2UtYnl0ZXM=",
                        "usage": {"input_tokens": 2, "output_tokens": 5},
                    },
                    {
                        "type": "image_generation.completed",
                        "b64_json": "aW1hZ2UtYnl0ZXM=",
                        "usage": {"input_tokens": 7, "output_tokens": 19},
                    },
                ]
            )
        return SimpleNamespace(
            data=[
                SimpleNamespace(
                    b64_json="aW1hZ2UtYnl0ZXM=", url=None, revised_prompt=None
                )
            ],
            usage=SimpleNamespace(input_tokens=7, output_tokens=19),
        )

    client = SimpleNamespace(images=SimpleNamespace(generate=generate))
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: client)
    args["stream"] = stream
    _, span = _run(monkeypatch, tool, args)
    assert len(calls) == 1
    assert span.attributes["gen_ai.usage.input_tokens"] == 7
    assert span.attributes["gen_ai.usage.output_tokens"] == 19
    assert span.attributes["uag.image.generated_count"] == 1


def test_image_prompt_obeys_category_and_secret_redaction(monkeypatch, image_tool):
    tool, args = image_tool
    args["prompt"] = "draw a bird; api_key=NEVER_EXPORT_THIS_KEY"
    _, span = _run(monkeypatch, tool, args)
    assert "NEVER_EXPORT_THIS_KEY" not in str(dict(span.attributes))
    assert "gen_ai.tool.call.arguments" in span.attributes


@pytest.mark.parametrize("count", [1, 2])
def test_real_grok_protobuf_usage_is_recorded_once_per_request(
    monkeypatch, image_tool, count
):
    from xai_sdk.image import BaseImageResponse
    from xai_sdk.proto import image_pb2, usage_pb2
    from uagent.tools import generate_grok

    tool, args = image_tool
    proto = image_pb2.ImageResponse(
        usage=usage_pb2.SamplingUsage(
            prompt_tokens=11, completion_tokens=23, cost_in_usd_ticks=2500000000
        )
    )
    for _ in range(count):
        proto.images.add(base64="aW1hZ2UtYnl0ZXM=", respect_moderation=True)
    responses = [BaseImageResponse(proto, index) for index in range(count)]
    client = SimpleNamespace(
        image=SimpleNamespace(
            sample=lambda **kwargs: responses[0],
            sample_batch=lambda **kwargs: responses,
        )
    )
    monkeypatch.setattr(
        generate_grok,
        "_get_grok_client_and_model",
        lambda: (client, "grok-imagine-image"),
    )
    monkeypatch.setattr(tool, "_get_provider", lambda: "grok")
    monkeypatch.setattr(tool, "_get_image_depname", lambda *args: "grok-imagine-image")
    args["n"] = count
    _, span = _run(monkeypatch, tool, args)
    assert span.attributes["gen_ai.usage.input_tokens"] == 11
    assert span.attributes["gen_ai.usage.output_tokens"] == 23
    assert span.attributes["uag.image.generated_count"] == count
    assert span.attributes["uag.image.cost_usd"] == pytest.approx(0.25)


def test_unreported_protobuf_usage_does_not_create_zero_counts(monkeypatch, image_tool):
    from xai_sdk.image import BaseImageResponse
    from xai_sdk.proto import image_pb2
    from uagent.runtime.observability.image_generation import (
        record_image_response_usage,
    )

    tool, args = image_tool
    proto = image_pb2.ImageResponse()
    proto.images.add(base64="aW1hZ2UtYnl0ZXM=")
    response = BaseImageResponse(proto, 0)

    def provider(**kwargs):
        record_image_response_usage(response)
        return {"b64_list": ["aW1hZ2UtYnl0ZXM="], "url_list": [], "items": []}

    monkeypatch.setattr(tool, "_run_openai_images", provider)
    _, span = _run(monkeypatch, tool, args)
    assert "gen_ai.usage.input_tokens" not in span.attributes
    assert "gen_ai.usage.output_tokens" not in span.attributes

    assert "uag.image.cost_usd" not in span.attributes


def test_reported_zero_cost_is_distinct_from_unreported_cost(monkeypatch, image_tool):
    from xai_sdk.image import BaseImageResponse
    from xai_sdk.proto import image_pb2, usage_pb2
    from uagent.runtime.observability.image_generation import (
        record_image_response_usage,
    )

    tool, args = image_tool
    proto = image_pb2.ImageResponse(usage=usage_pb2.SamplingUsage(cost_in_usd_ticks=0))
    proto.images.add(base64="aW1hZ2UtYnl0ZXM=")

    def provider(**kwargs):
        record_image_response_usage(BaseImageResponse(proto, 0))
        return {"b64_list": ["aW1hZ2UtYnl0ZXM="], "url_list": [], "items": []}

    monkeypatch.setattr(tool, "_run_openai_images", provider)
    _, span = _run(monkeypatch, tool, args)
    assert span.attributes["uag.image.cost_usd"] == 0.0
    assert "gen_ai.usage.input_tokens" not in span.attributes
