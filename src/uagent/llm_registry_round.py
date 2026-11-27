"""Provider-registry round path: one simple chat round through a
registered provider adapter (split out of uagent_llm).
"""

from __future__ import annotations

from typing import Any, Mapping
import os

from .env_utils import env_get
from .llm_helpers import _auto_low_quality, _bump_effort, _env_default_on
from .llm_message_helpers import _get_shrink_max_tokens
from .providers.responses_runtime import _responses_session_generation
from .runtime.context_plan_builder import context_plan_matches
from .runtime.round_contracts import RoundTransportSelection
from .runtime.tool_discovery import MANAGEMENT_TOOL_NAMES as _MGMT_TOOLS
from .tools.llm_tool_narrowing import resolve_tool_discovery
from .llm_responses_runtime import (
    _sync_registry_responses_terminal,
    _try_responses_remote_recovery,
)
from .llm_turn_context import _build_round_context_plan


class _CoreInterruptCancellationToken:
    """Combine the provider token with the application's Stop/F12 signal."""

    def __init__(self, core: Any, delegate: Any = None) -> None:
        self._core = core
        self._delegate = delegate

    def is_cancelled(self) -> bool:
        try:
            from .llm_helpers import stream_stop_requested

            if stream_stop_requested(self._core):
                return True
        except Exception:
            pass
        is_cancelled = getattr(self._delegate, "is_cancelled", None)
        if callable(is_cancelled):
            try:
                return bool(is_cancelled())
            except Exception:
                return False
        return False


def _registry_stream_event_observer(
    core: Any,
    *,
    streaming: bool,
    progress_observer: Any = None,
) -> Any:
    """Render registry text deltas through the host's standard stream hook."""
    snapshot = ""
    try:
        core._registry_stream_output_rendered = False
        core._registry_stream_line_open = False
    except Exception:
        pass

    def observe(event: Any) -> None:
        nonlocal snapshot
        if callable(progress_observer):
            try:
                progress_observer(event)
            except Exception:
                # Progress rendering must not prevent text delivery or fail
                # the provider round.
                pass
        if not streaming:
            return
        event_type = str(getattr(event, "type", "") or "")
        data = getattr(event, "data", {})
        if not hasattr(data, "get"):
            return
        text = str(data.get("text") or "")
        if event_type == "TextSnapshot":
            if text.startswith(snapshot):
                text = text[len(snapshot) :]
            # A terminal cannot retract an already printed prefix. If the
            # provider revises it, emit the new snapshot as best effort.
            snapshot = str(data.get("text") or "")
        elif event_type != "TextDelta":
            return
        if not text:
            return
        is_web = bool(getattr(core, "_is_web", False))
        log_message = getattr(core, "log_message", None)
        render_delta = getattr(core, "print_stream_delta", None)
        if is_web and callable(log_message):
            log_message({"type": "assistant_stream_delta", "delta": text})
            rendered = True
        elif callable(render_delta):
            render_delta(text)
            rendered = True
        else:
            rendered = False
        if rendered:
            try:
                core._registry_stream_output_rendered = True
                core._registry_stream_line_open = not is_web and not text.endswith("\n")
            except Exception:
                pass

    return observe


def _finish_registry_stream(core: Any, *, terminal_status: str) -> None:
    """Close the host stream surface after a registry response terminates."""
    if not bool(getattr(core, "_registry_stream_output_rendered", False)):
        return
    if bool(getattr(core, "_is_web", False)):
        log_message = getattr(core, "log_message", None)
        if callable(log_message):
            event_type = (
                "assistant_stream_interrupted"
                if terminal_status in {"cancelled", "interrupted"}
                else "assistant_stream_end"
            )
            try:
                log_message({"type": event_type})
            except Exception:
                pass
        return
    if bool(getattr(core, "_registry_stream_line_open", False)):
        close_line = getattr(core, "print_stream_delta", None)
        if callable(close_line):
            try:
                close_line("\n")
            except Exception:
                pass
        try:
            core._registry_stream_line_open = False
        except Exception:
            pass


def _select_registry_tool_specs(
    tool_specs: Any,
    *,
    discovery: Any,
    use_responses_api: bool,
    round_count: int,
) -> tuple[Any, ...]:
    """Apply the discovery-mode tool surface to registry requests."""
    specs = tuple(tool_specs or ())
    if discovery.uses_native_search and use_responses_api:
        # Native Responses tool search discovers tools server-side. Sending the
        # local catalog controls alongside regular schemas defeats that path.
        return tuple(
            spec
            for spec in specs
            if not (
                isinstance(spec, dict)
                and isinstance(spec.get("function"), dict)
                and spec["function"].get("name") in _MGMT_TOOLS
            )
        )
    if round_count <= 1 and discovery.uses_management_bootstrap(
        use_responses_api=use_responses_api
    ):
        management_specs = tuple(
            spec
            for spec in specs
            if isinstance(spec, dict)
            and isinstance(spec.get("function"), dict)
            and spec["function"].get("name") in _MGMT_TOOLS
        )
        if management_specs:
            return management_specs
    return specs


def _try_registry_simple_chat_round(
    *,
    provider: str,
    client: Any,
    depname: str,
    call_messages: list[dict[str, Any]],
    core: Any,
    use_responses_api: bool,
    stream_responses: bool,
    send_tools_this_round: bool,
    round_count: int,
    transport_selection: RoundTransportSelection | None = None,
    registry_route: Any | None = None,
    tool_discovery: Any | None = None,
) -> tuple[bool, str, str, list[dict[str, Any]]] | None:
    """Run the default-on registry path for OpenAI-compatible rounds.

    Explicit ``off`` values restore the legacy path. Unsupported providers and
    intentionally deferred modes also retain their established fallback.
    """
    if transport_selection is not None:
        use_responses_api = transport_selection.use_responses_api
        stream_responses = transport_selection.streaming
    discovery = tool_discovery
    if discovery is None:
        discovery = resolve_tool_discovery(
            provider=provider,
            depname=depname,
            # Capability is needed for both transports because the registry may
            # use Chat Completions while bootstrapping tool discovery.
            use_responses_api=True,
        )
    if registry_route is None:
        from .runtime.provider_round_dispatcher import registry_round_allowed

        if not registry_round_allowed(
            provider=provider,
            configured_providers=env_get("UAGENT_PROVIDER_REGISTRY", "") or "",
            use_responses_api=use_responses_api,
            responses_enabled=_env_default_on("UAGENT_PROVIDER_REGISTRY_RESPONSES"),
            send_tools=send_tools_this_round,
            tools_enabled=_env_default_on("UAGENT_PROVIDER_REGISTRY_TOOLS"),
            has_context_tools=bool(getattr(core, "context_tool_specs", None)),
            uses_legacy_catalog=(use_responses_api and discovery.uses_legacy_catalog),
        ):
            return None
    elif not getattr(registry_route, "allowed", False):
        return None
    try:
        from .providers.runtime_registry import build_provider_runtime_registry
        from .runtime.round_contracts import RoundIdentifiers
        from .runtime.round_identity import (
            CredentialStoreWorkspaceKeyProvider,
            RoundIdentityFactory,
        )
        from .runtime.round_orchestrator import RoundOrchestrator

        marker = f"registry-{provider}-{round_count}-{id(core)}"
        identifiers = RoundIdentifiers(
            turn_id=marker,
            round_id=marker,
            attempt_id=marker,
            request_id=marker,
            stream_id=marker,
            session_generation=_responses_session_generation(core),
        )
        workspace_id = str(getattr(core, "workdir", "") or os.getcwd())
        identity_factory = getattr(core, "round_identity_factory", None)
        supplied_key_provider = getattr(identity_factory, "key_provider", None)
        if not callable(
            getattr(identity_factory, "projection_id", None)
        ) or not callable(getattr(supplied_key_provider, "get_key", None)):
            key_provider = CredentialStoreWorkspaceKeyProvider()
            identity_factory = RoundIdentityFactory(workspace_id, key_provider)
        else:
            key_provider = supplied_key_provider
        tool_specs = getattr(core, "context_tool_specs", None) or ()
        if send_tools_this_round and not tool_specs:
            from . import tools as _tools

            tool_specs = tuple(_tools.get_tool_specs() or ())
        if send_tools_this_round:
            tool_specs = _select_registry_tool_specs(
                tool_specs,
                discovery=discovery,
                use_responses_api=use_responses_api,
                round_count=round_count,
            )
        if provider == "sarashina" and send_tools_this_round and round_count <= 1:
            from .runtime.chat_tool_policy import (
                initial_sarashina_chat_completion_tools,
            )

            tool_specs = tuple(initial_sarashina_chat_completion_tools(tool_specs))
        if send_tools_this_round and not use_responses_api:
            from .runtime.chat_tool_policy import (
                limit_chat_completion_tools as _limit_chat_completion_tools,
            )
            from . import tools as _tools

            tool_specs = tuple(
                _limit_chat_completion_tools(list(tool_specs), call_messages)
            )
            _tools.log_tools_being_sent(tool_specs, where="registry_chatcompletions")
        prepared_plan = getattr(core, "context_plan", None)
        if context_plan_matches(
            prepared_plan,
            call_messages,
            tool_specs if send_tools_this_round else (),
            history_revision=str(getattr(core, "history_revision", "") or ""),
            schema_revision=str(getattr(core, "context_schema_revision", "1") or "1"),
        ):
            # Reuse the standard hand-off when ContextManager already prepared
            # the exact post-transform context for this provider round.
            plan = prepared_plan
        else:
            plan = _build_round_context_plan(
                provider=provider,
                depname=depname,
                call_messages=call_messages,
                core=core,
                workspace_id=workspace_id,
                tool_specs=tool_specs if send_tools_this_round else (),
                key_provider=key_provider,
                history_revision=str(getattr(core, "history_revision", "") or ""),
                schema_revision=str(
                    getattr(core, "context_schema_revision", "1") or "1"
                ),
            )
        core.context_plan = plan
        transport = "responses" if use_responses_api else "chat_completions"
        from .providers.openai_projection_policy import build_openai_projection

        projection = build_openai_projection(
            provider=provider,
            model=depname,
            transport=transport,
            messages=call_messages,
            send_tools=send_tools_this_round,
            compaction_threshold=_get_shrink_max_tokens(depname),
        )
        options = projection.options
        reasoning = projection.reasoning
        auto_user_text = projection.auto_user_text
        effort_used = projection.effort_used
        if use_responses_api:
            from .providers.responses_manager import get_responses_capabilities

            state = getattr(core, "responses_state", {})
            previous_id = (
                state.get("previous_response_id") if isinstance(state, dict) else None
            )
            if (
                isinstance(previous_id, str)
                and previous_id.startswith("resp_")
                and get_responses_capabilities(provider).previous_response_id
            ):
                options["previous_response_id"] = previous_id
        registry = build_provider_runtime_registry(
            provider=provider,
            client=client,
            model=depname,
            identifiers=identifiers,
            transport=transport,
            streaming=stream_responses,
            transport_selection=transport_selection,
            options=options,
        )
        foundry_progress_observer: Any = None
        if provider.strip().lower() == "foundry_local":
            from .providers.llm_foundry_local import FoundryLocalProgressObserver

            foundry_progress_observer = FoundryLocalProgressObserver(core)

        registry_event_observer = _registry_stream_event_observer(
            core,
            # Auto reasoning can retry a low-quality answer after the first
            # attempt completes. Do not publish that provisional attempt; the
            # final accepted answer is rendered once by the compatibility loop.
            streaming=(
                stream_responses and str(reasoning or "").strip().lower() != "auto"
            ),
            progress_observer=foundry_progress_observer,
        )

        cancellation = _CoreInterruptCancellationToken(
            core,
            delegate=getattr(core, "cancellation_token", None),
        )
        result = (
            RoundOrchestrator(registry)
            .run(
                plan,
                provider=provider,
                session={
                    "identity_factory": identity_factory,
                    "responses_runtime": getattr(core, "responses_runtime", None),
                    "recovery_hint": getattr(core, "last_recovery_update", None),
                },
                cancellation=cancellation,
                on_event=registry_event_observer,
            )
            .result
        )
        if (
            reasoning == "auto"
            and effort_used is not None
            and result.status == "completed"
            and not result.tool_calls
            and _auto_low_quality(auto_user_text, result.assistant_text)
        ):
            from dataclasses import replace

            from .runtime.round_runtime import RoundAttemptBudget, RetryRequest

            next_effort = _bump_effort(effort_used)
            retry_budget = RoundAttemptBudget(
                total_limit=1, reason_limits={"feature_fallback": 1}
            )
            if next_effort and retry_budget.try_consume(
                RetryRequest("feature_fallback", "reasoning auto quality retry")
            ):
                retry_options = dict(options)
                if use_responses_api:
                    retry_options["reasoning"] = {"effort": next_effort}
                else:
                    retry_options["reasoning_effort"] = next_effort
                retry_identifiers = replace(
                    identifiers,
                    attempt_id=f"{identifiers.attempt_id}-auto-retry",
                    request_id=f"{identifiers.request_id}-auto-retry",
                    stream_id=f"{identifiers.stream_id}-auto-retry",
                )
                retry_registry = build_provider_runtime_registry(
                    provider=provider,
                    client=client,
                    model=depname,
                    identifiers=retry_identifiers,
                    transport=transport,
                    streaming=stream_responses,
                    transport_selection=transport_selection,
                    options=retry_options,
                )
                result = (
                    RoundOrchestrator(retry_registry)
                    .run(
                        plan,
                        provider=provider,
                        session={
                            "identity_factory": identity_factory,
                            "responses_runtime": getattr(
                                core, "responses_runtime", None
                            ),
                            "recovery_hint": getattr(
                                core, "last_recovery_update", None
                            ),
                        },
                        cancellation=cancellation,
                        on_event=registry_event_observer,
                    )
                    .result
                )
                core.round_attempt_budget = retry_budget
                core.last_auto_reasoning_retry = {
                    "initial_effort": effort_used,
                    "retry_effort": next_effort,
                }
        _finish_registry_stream(core, terminal_status=result.status)
        if result.status == "failed":
            core.context_projection_id = result.projection_id
            from .runtime.context_recovery import ContextRecoveryManager
            from .runtime.llm_error_classifier import LLMErrorClassifier
            from .runtime.round_runtime import RoundAttemptBudget, RetryRequest

            error_text = str((result.error or {}).get("message") or "")
            if (
                LLMErrorClassifier().classify(RuntimeError(error_text)).kind
                == "context_overflow"
            ):
                budget = RoundAttemptBudget(total_limit=1)
                if budget.try_consume(
                    RetryRequest("context_overflow", "registry local recovery")
                ):
                    recovery = ContextRecoveryManager().plan(
                        context_plan=plan,
                        projection_id=result.projection_id,
                        error_text=error_text,
                        attempt_id=identifiers.attempt_id,
                    )
                    if use_responses_api:
                        from dataclasses import replace

                        remote_plan = replace(
                            recovery,
                            strategy="provider_compact",
                            remote_session_mutation=True,
                        )
                        if _try_responses_remote_recovery(core, client, remote_plan):
                            return None
                    recovery_hint = {
                        "recovery_id": recovery.recovery_id,
                        "strategy": recovery.strategy,
                        "omitted_message_indexes": recovery.omitted_message_indexes,
                        "omitted_message_ids": recovery.omitted_message_ids,
                        "source_plan_id": recovery.plan_id,
                    }
                    core.last_recovery_plan = recovery
                    result = (
                        RoundOrchestrator(registry)
                        .run(
                            plan,
                            provider=provider,
                            session={
                                "identity_factory": identity_factory,
                                "responses_runtime": getattr(
                                    core, "responses_runtime", None
                                ),
                                "recovery_hint": recovery_hint,
                            },
                            cancellation=cancellation,
                            on_event=foundry_progress_observer,
                        )
                        .result
                    )
                    core.context_projection_id = result.projection_id
        # A non-completed registry response is not a usable assistant turn.
        # Let the established provider path handle the request so registry
        # adapter failures do not silently terminate the user operation.
        if result.status != "completed":
            if use_responses_api:
                _sync_registry_responses_terminal(core, result.status)
            if result.status in {"cancelled", "interrupted"}:
                # Return an empty, handled result so dispatch does not fall
                # through to the legacy path and issue a second request. The
                # round loop consumes the pending Stop and injects its normal
                # stop prompt immediately after dispatch.
                try:
                    core._last_round_reason = "interrupted"
                except Exception:
                    pass
                return True, "", "", []
            try:
                from .runtime.logging_setup import log_event

                log_event(
                    "llm.registry_fallback",
                    provider=provider,
                    model=depname,
                    registry_status=result.status,
                )
            except Exception:
                pass
            return None

        # A completed registry response without text or tool calls is not a
        # usable assistant turn. Let the established provider path retry it
        # rather than treating an empty response as a successful final answer.
        if (
            not result.assistant_text
            and not result.tool_calls
            and not result.continuation_update
        ):
            return None
        if result.continuation_update and isinstance(
            getattr(core, "responses_state", None), dict
        ):
            core.responses_state["previous_response_id"] = result.continuation_update[
                "response_id"
            ]
            # Persist the runtime generation with the response ID. Otherwise
            # a restart restores the response but resets the ToolCallKey
            # generation used to validate its tool outputs.
            runtime = getattr(core, "responses_runtime", None)
            if runtime is not None:
                try:
                    core.responses_state["session_generation"] = int(
                        getattr(runtime, "session_generation", 0) or 0
                    )
                except (TypeError, ValueError):
                    pass
        elif use_responses_api:
            _sync_registry_responses_terminal(core, result.status)
        from .runtime.provider_round_dispatcher import (
            registry_result_to_legacy_tuple,
        )

        normalized_result = registry_result_to_legacy_tuple(result)
        if normalized_result is None:
            return None
        # The compatibility round loop publishes usage from the legacy core
        # snapshot after this adapter returns. Registry-backed rounds carry
        # provider-reported usage in RoundSummary instead, so bridge that
        # per-request delta back to the core or the CLI status line sees only
        # stale/empty legacy usage.
        summary = getattr(result, "summary", None)
        usage_delta = getattr(summary, "usage_delta", None)
        if isinstance(usage_delta, Mapping):
            usage_snapshot = {
                key[: -len("_delta")]: value
                for key, value in usage_delta.items()
                if isinstance(key, str)
                and key.endswith("_delta")
                and type(value) is int
                and value >= 0
            }
            try:
                core._last_responses_usage = usage_snapshot
            except (AttributeError, TypeError):
                pass
        if use_responses_api and result.tool_calls and result.reasoning_text:
            # Registry rounds collect stream events instead of displaying them
            # during execution. Preserve the reasoning summary on tool turns,
            # which do not reach the final-answer renderer.
            from .runtime.reasoning_renderer import render_tool_call_reasoning

            render_tool_call_reasoning(
                result.reasoning_text,
                provider=provider.capitalize(),
                core=core,
            )
        return normalized_result
    except Exception:
        return None
