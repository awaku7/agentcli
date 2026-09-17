"""Inception adapter for the provider-neutral round runtime."""

from __future__ import annotations

from typing import Any, Iterator, Mapping

from ..runtime.provider_context import (
    apply_recovery_projection,
    project_messages_for_provider,
)
from ..runtime.round_contracts import (
    CancellationToken,
    ContextPlan,
    ProviderProjection,
    RoundIdentifiers,
    SerializedRequest,
    StreamEvent,
)
from ..runtime.round_identity import canonical_json
from .llm_inception import inception_stream_events


class InceptionProviderRuntime:
    """Translate a plan into Mercury Chat Completions and normalized events."""

    def __init__(
        self,
        *,
        client: Any,
        model: str,
        identifiers: RoundIdentifiers,
        options: Mapping[str, Any] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        from ..runtime.capability_resolver import CapabilityResolver

        self.capabilities = CapabilityResolver().resolve(
            "inception", self._model, "chat_completions"
        )
        self._identifiers = identifiers
        self._options = dict(options or {})

    def project(
        self, plan: ContextPlan, session: Mapping[str, Any]
    ) -> ProviderProjection:
        from ..runtime.message_transform import MessageTransformPipeline

        source_messages = apply_recovery_projection(
            plan.messages,
            session.get("recovery_hint"),
        )
        transformed = MessageTransformPipeline().apply(
            source_messages,
            translator=session.get("translator"),
        )
        messages = project_messages_for_provider(
            [dict(message) for message in transformed.messages],
            provider="inception",
            model=self._model,
        )
        identity_factory = session.get("identity_factory")
        make_projection_id = getattr(identity_factory, "projection_id", None)
        if not callable(make_projection_id):
            raise ValueError(
                "session must provide an identity_factory for projection IDs"
            )
        projection_id = make_projection_id(
            canonical_json(
                {
                    "plan_id": plan.plan_id,
                    "provider": "inception",
                    "model": self._model,
                    "messages": messages,
                    "transforms": transformed.applied,
                }
            )
        )
        return ProviderProjection(
            plan_id=plan.plan_id,
            projection_id=projection_id,
            provider="inception",
            model=self._model,
            transport="chat_completions",
            messages=tuple(messages),
            tool_specs=plan.tool_specs,
            options=self._options,
            metadata={"transforms": transformed.applied},
        )

    def serialize(self, projection: ProviderProjection) -> SerializedRequest:
        payload = {
            "model": projection.model,
            "messages": list(projection.messages),
            **projection.options,
        }
        if projection.tool_specs:
            payload["tools"] = list(projection.tool_specs)
            payload["tool_choice"] = "auto"
        return SerializedRequest(
            identifiers=self._identifiers,
            plan_id=projection.plan_id,
            projection_id=projection.projection_id,
            provider="inception",
            model=projection.model,
            payload=payload,
        )

    def run(
        self, request: SerializedRequest, cancellation: CancellationToken
    ) -> Iterator[StreamEvent]:
        stream = self._client.chat.completions.create(**request.payload, stream=True)
        extra_body = request.payload.get("extra_body")
        yield from inception_stream_events(
            stream,
            identifiers=request.identifiers,
            diffusing=bool(
                isinstance(extra_body, Mapping) and extra_body.get("diffusing", False)
            ),
            cancellation=cancellation,
        )
